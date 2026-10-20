"""Inspect task: annotate neuron identities in the sample clip, scored against painted identity marks.

Run from the repository root, for example:
    uv run --group evals inspect eval evals/identity/task.py --model mockllm/model -T agent=stub_oracle
    CLAUDE_CODE_OAUTH_TOKEN=... uv run --group evals inspect eval evals/identity/task.py \
        --model mockllm/model -T agent=claude_cli -T model=haiku -T effort=xhigh
The default agent, claude_cli, runs the Claude Code CLI in the sandbox with a subscription token from
`claude setup-token`; Inspect makes no model calls, so the Inspect --model is a placeholder. The agent
`claude` instead routes model calls through Inspect and needs an Anthropic API key.
"""

import json
import os
import time
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.util import sandbox
from inspect_swe import claude_code
from jsonschema import Draft202012Validator

from evals.identity.prompt import PROMPT
from evals.identity.stubs import OUTPUT, build
from neuron_tracking.identity import IdentityMarks, evaluate

ROOT = Path(__file__).resolve().parents[2]
MARKS = ROOT / "data" / "eval" / "identity_marks.json"
SCHEMA = ROOT / "annotations.schema.json"
VIDEO = ROOT / "data" / "IMG_6128.AVI"


CLAUDE_CODE_VERSION = "2.1.305"
WORKSPACE_FILES = {
    "/workspace/annotate.md": ROOT / "tasks/identity/annotate.md",
    "/workspace/format.md": ROOT / "tasks/identity/format.md",
    "/workspace/annotations.schema.json": SCHEMA,
    "/workspace/IMG_6128.AVI": VIDEO,
    "/workspace/photo_2026-10-19_14-30-28.jpg": ROOT / "data/photo_2026-10-19_14-30-28.jpg",
    "/workspace/pyproject.toml": ROOT / "pyproject.toml",
    "/workspace/uv.lock": ROOT / "uv.lock",
    "/workspace/.python-version": ROOT / ".python-version",
    "/workspace/neuron_tracking/annotations.py": ROOT / "neuron_tracking/annotations.py",
    "/workspace/neuron_tracking/render.py": ROOT / "neuron_tracking/render.py",
}
# Runs as root in the sandbox before the agent starts. Only the renderer is exposed; evaluation and
# checking code is never uploaded, and the agent user owns the workspace.
SETUP = f"""
set -euo pipefail
cd /workspace
useradd --create-home --shell /bin/bash agent
sed -i '/^neuron-check\\|^neuron-identity\\|^neuron-eval-frames/d' pyproject.toml
printf '# Renderer workspace\\n' > README.md
pip install --quiet --no-cache-dir uv nodejs-wheel
UV_PROJECT_ENVIRONMENT=/workspace/.venv uv sync --locked --no-dev --group agent
npm install --global --silent @anthropic-ai/claude-code@{CLAUDE_CODE_VERSION}
ln -sf "$(npm prefix -g)/bin/claude" /usr/local/bin/claude
mkdir -p output
chown -R agent:agent /workspace
"""


@solver
def stub(mode: str):
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        marks = IdentityMarks.model_validate_json(MARKS.read_text())
        if mode == "invalid":
            text = '{"schema_version": 1}'
        else:
            text = build(marks, VIDEO, mode=mode)
        await sandbox().write_file(OUTPUT, text)
        return state

    return solve


@solver
def claude_cli(model: str, effort: str | None, minutes: int):
    """Run `claude -p` in the sandbox, authenticated by a subscription token from the host environment."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        if not token:
            raise RuntimeError("Set CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) to run agent=claude_cli")
        command = ["claude", "-p", state.input_text, "--model", model, "--dangerously-skip-permissions",
                   "--output-format", "stream-json", "--verbose"]
        if effort:
            command += ["--effort", effort]
        started = time.time()
        try:
            result = await sandbox().exec(command, cwd="/workspace", user="agent",
                                          env={"CLAUDE_CODE_OAUTH_TOKEN": token, "HOME": "/home/agent",
                                               "PATH": "/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin"},
                                          timeout=minutes * 60, timeout_retry=False)
            stream, returncode, stderr = result.stdout, result.returncode, result.stderr
        except TimeoutError:
            stream, returncode, stderr = "", None, f"timed out after {minutes} minutes"
        folder = ROOT / "runs" / "transcripts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%dT%H%M%S')}_{model}_{effort or 'default'}.jsonl"
        path.write_text(stream)
        transcript().info({"returncode": returncode, "seconds": round(time.time() - started), "stream": str(path),
                           "stderr": stderr[-2000:]}, source="claude_cli")
        return state

    return solve


@scorer(metrics={"*": [mean()]})
def identity_scorer():
    marks = IdentityMarks.model_validate_json(MARKS.read_text())
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))

    async def score(state: TaskState, target: Target) -> Score:
        try:
            text = await sandbox().read_file(OUTPUT)
        except FileNotFoundError:
            return failed("output/annotations.json was not written")
        try:
            errors = sorted(validator.iter_errors(json.loads(text)), key=lambda error: list(error.path))
        except json.JSONDecodeError as error:
            return failed(f"annotations.json is not JSON: {error}")
        if errors:
            return failed(f"schema: {errors[0].message[:300]} at {list(errors[0].path)[:6]}")
        report = evaluate(text, marks)
        if not report["valid"]:
            return failed(report["reason"])
        same, different, covered = report["same_cell"], report["different_cell"], report["marks_with_a_neuron"]
        value = {
            "valid": 1.0,
            "same_cell": same["passed"] / same["total"],
            "different_cell": different["passed"] / different["total"],
            "marks_covered": covered["passed"] / covered["total"],
        }
        value["all_pass"] = float(not report["failures"] and value["marks_covered"] == 1.0)
        return Score(value=value, explanation=json.dumps({key: report[key] for key in report if key != "valid"}), metadata=report)

    return score


def failed(reason: str) -> Score:
    value = {"valid": 0.0, "same_cell": 0.0, "different_cell": 0.0, "marks_covered": 0.0, "all_pass": 0.0}
    return Score(value=value, explanation=reason)


@task
def identity(agent: str = "claude_cli", model: str = "haiku", effort: str | None = None, minutes: int = 30,
             compose: str = str(Path(__file__).with_name("compose.yaml"))) -> Task:
    if agent == "claude_cli":
        solver_ = claude_cli(model, effort, minutes)
    elif agent == "claude":
        solver_ = claude_code(cwd="/workspace", user="agent", effort=effort, permission_mode="bypassPermissions")
    elif agent.startswith("stub_"):
        solver_ = stub(agent.removeprefix("stub_"))
    else:
        raise ValueError(f"Unknown agent {agent!r}; use claude_cli, claude, stub_oracle, stub_empty or stub_invalid")
    needs_workspace = not agent.startswith("stub_")
    sample = Sample(input=PROMPT, files={k: str(v) for k, v in WORKSPACE_FILES.items()} if needs_workspace else None,
                    setup=SETUP if needs_workspace else None)
    return Task(
        dataset=[sample],
        solver=solver_,
        scorer=identity_scorer(),
        sandbox=("docker", str(ROOT / compose)),
        time_limit=minutes * 60,
    )
