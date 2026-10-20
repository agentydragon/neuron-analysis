"""Inspect task: annotate neuron identities in the sample clip, scored against painted identity marks.

Two tasks: `identity` (the whole clip) and `identity_clips` (one short clip per marked group, run as
parallel samples, each scored against only its own group's marks).

Run from the repository root, for example:
    uv run --group evals inspect eval evals/identity/task.py --model mockllm/model -T agent=stub_oracle
    uv run --group evals inspect eval evals/identity/task.py@identity_clips --model mockllm/model -T agent=stub_oracle
    CLAUDE_CODE_OAUTH_TOKEN=... uv run --group evals inspect eval evals/identity/task.py \
        --model mockllm/model -T agent=claude_cli -T model=haiku -T effort=xhigh
The default agent, claude_cli, runs the Claude Code CLI in the sandbox with a subscription token from
`claude setup-token`; Inspect makes no model calls, so the Inspect --model is a placeholder. The agent
`claude` instead routes model calls through Inspect and needs an Anthropic API key.
"""

import json
import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path

import av
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.util import sandbox
from inspect_swe import claude_code
from jsonschema import Draft202012Validator

from evals.identity.prompt import prompt
from evals.identity.stubs import OUTPUT, build
from neuron_tracking.clips import clip_marks, clip_range, cut_clip
from neuron_tracking.identity import IdentityMarks, evaluate

ROOT = Path(__file__).resolve().parents[2]
MARKS = ROOT / "data" / "eval" / "identity_marks.json"
SCHEMA = ROOT / "annotations.schema.json"
VIDEO = ROOT / "data" / "IMG_6128.AVI"


CLAUDE_CODE_VERSION = "2.1.305"


@dataclass(frozen=True)
class Variant:
    """One sample: the video the agent gets, and the marks its output is scored against."""

    id: str
    video: Path
    video_name: str
    marks: IdentityMarks


def full_variant() -> Variant:
    return Variant("full", VIDEO, VIDEO.name, IdentityMarks.model_validate_json(MARKS.read_text()))


def clip_variants(groups: str | None, margin: int) -> list[Variant]:
    """A lossless clip around each marked group (plus margin frames), cached under runs/clips."""
    marks = IdentityMarks.model_validate_json(MARKS.read_text())
    with av.open(str(VIDEO)) as container:
        frame_count = container.streams.video[0].frames
    wanted = groups.split(",") if groups else [group.name for group in marks.groups]
    unknown = set(wanted) - {group.name for group in marks.groups}
    if unknown:
        raise ValueError(f"Unknown groups {sorted(unknown)}; marked groups are {[g.name for g in marks.groups]}")
    variants = []
    for group in (group for group in marks.groups if group.name in wanted):
        first, last = clip_range(group, margin, frame_count)
        clip = ROOT / "runs" / "clips" / f"{group.name}_m{margin}" / "clip.avi"
        if not clip.exists():
            cut_clip(VIDEO, first, last, clip)
        variants.append(Variant(group.name, clip, clip.name, clip_marks(marks, group.name, first, clip)))
    return variants


def workspace_files(variant: Variant) -> dict[str, str]:
    return {
        "/workspace/annotate.md": ROOT / "tasks/identity/annotate.md",
        "/workspace/format.md": ROOT / "tasks/identity/format.md",
        "/workspace/annotations.schema.json": SCHEMA,
        f"/workspace/{variant.video_name}": variant.video,
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
def stub(mode: str, variants: dict[str, Variant]):
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        variant = variants[str(state.sample_id)]
        if mode == "invalid":
            text = '{"schema_version": 1}'
        else:
            text = build(variant.marks, variant.video, mode=mode)
        await sandbox().write_file(OUTPUT, text)
        return state

    return solve


async def read_or_empty(path: str) -> str:
    try:
        return await sandbox().read_file(path)
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


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
        # Output goes to files in the sandbox so a timeout still leaves a transcript to collect.
        shell = f"exec {shlex.join(command)} > /tmp/claude_stream.jsonl 2> /tmp/claude_stderr.txt"
        started = time.time()
        returncode: int | None = None
        try:
            result = await sandbox().exec(["bash", "-c", shell], cwd="/workspace", user="agent",
                                          env={"CLAUDE_CODE_OAUTH_TOKEN": token, "HOME": "/home/agent",
                                               "PATH": "/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin"},
                                          timeout=minutes * 60, timeout_retry=False)
            returncode = result.returncode
        except TimeoutError:
            pass
        stream, stderr = await read_or_empty("/tmp/claude_stream.jsonl"), await read_or_empty("/tmp/claude_stderr.txt")
        folder = ROOT / "runs" / "transcripts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%dT%H%M%S')}_{state.sample_id}_{model}_{effort or 'default'}.jsonl"
        path.write_text(stream)
        transcript().info({"returncode": returncode, "timed_out": returncode is None, "seconds": round(time.time() - started),
                           "stream": str(path), "stderr": stderr[-2000:]}, source="claude_cli")
        return state

    return solve


@scorer(metrics={"*": [mean()]})
def identity_scorer(variants: dict[str, Variant]):
    validator = Draft202012Validator(json.loads(SCHEMA.read_text()))

    async def score(state: TaskState, target: Target) -> Score:
        try:
            text = await sandbox().read_file(OUTPUT)
        except FileNotFoundError:
            return failed("output/annotations.json was not written")
        saved = ROOT / "runs" / "outputs" / f"{time.strftime('%Y%m%dT%H%M%S')}_{state.sample_id}.annotations.json"
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(text)
        try:
            document = json.loads(text)
            errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        except json.JSONDecodeError as error:
            return failed(f"annotations.json is not JSON: {error}")
        if errors:
            return failed(f"schema: {errors[0].message[:300]} at {list(errors[0].path)[:6]}")
        report = evaluate(text, variants[str(state.sample_id)].marks)
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
        report["neurons"] = len(document["neurons"])
        report["saved_annotations"] = str(saved)
        return Score(value=value, explanation=json.dumps({key: report[key] for key in report if key != "valid"}), metadata=report)

    return score


def failed(reason: str) -> Score:
    value = {"valid": 0.0, "same_cell": 0.0, "different_cell": 0.0, "marks_covered": 0.0, "all_pass": 0.0}
    return Score(value=value, explanation=reason)


def build_task(variants: list[Variant], agent: str, model: str, effort: str | None, minutes: int, compose: str) -> Task:
    by_id = {variant.id: variant for variant in variants}
    if agent == "claude_cli":
        solver_ = claude_cli(model, effort, minutes)
    elif agent == "claude":
        solver_ = claude_code(cwd="/workspace", user="agent", effort=effort, permission_mode="bypassPermissions")
    elif agent.startswith("stub_"):
        solver_ = stub(agent.removeprefix("stub_"), by_id)
    else:
        raise ValueError(f"Unknown agent {agent!r}; use claude_cli, claude, stub_oracle, stub_empty or stub_invalid")
    needs_workspace = not agent.startswith("stub_")
    samples = [
        Sample(
            id=variant.id,
            input=prompt(variant.video_name),
            files={path: str(source) for path, source in workspace_files(variant).items()} if needs_workspace else None,
            setup=SETUP if needs_workspace else None,
        )
        for variant in variants
    ]
    return Task(
        dataset=samples,
        solver=solver_,
        scorer=identity_scorer(by_id),
        sandbox=("docker", str(ROOT / compose)),
        time_limit=(minutes + 5) * 60,  # setup and scoring happen inside the sample limit
    )


COMPOSE = str(Path(__file__).with_name("compose.yaml"))


@task
def identity(agent: str = "claude_cli", model: str = "haiku", effort: str | None = None, minutes: int = 30,
             compose: str = COMPOSE) -> Task:
    return build_task([full_variant()], agent, model, effort, minutes, compose)


@task
def identity_clips(agent: str = "claude_cli", model: str = "haiku", effort: str | None = None, minutes: int = 20,
                   groups: str | None = None, margin: int = 2, compose: str = COMPOSE) -> Task:
    """Short clips around each marked group (all by default, or e.g. groups=24-32,66-72)."""
    return build_task(clip_variants(groups, margin), agent, model, effort, minutes, compose)
