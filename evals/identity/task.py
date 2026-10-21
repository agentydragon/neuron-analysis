"""Inspect task: annotate cell identities in the sample clip, scored against painted identity marks.

Two tasks: `identity` (the whole clip) and `identity_clips` (one short clip per marked group, run as
parallel samples, each scored against only its own group's marks).

Run from the repository root, for example:
    uv run --group evals inspect eval evals/identity/task.py@identity --model mockllm/model -T agent=stub_oracle
    uv run --group evals inspect eval evals/identity/task.py@identity_clips --model mockllm/model -T agent=stub_oracle
    CLAUDE_CODE_OAUTH_TOKEN=... uv run --group evals inspect eval evals/identity/task.py@identity \
        --model mockllm/model -T agent=claude_cli -T model=haiku -T effort=xhigh
The default agent, claude_cli, runs the Claude Code CLI in the sandbox with a subscription token from
`claude setup-token`; codex_cli runs native Codex with a mounted ChatGPT auth file (use run-codex.sh).
For both native agents, Inspect makes no model calls, so its --model is a placeholder. The agent
`claude` instead routes model calls through Inspect and needs an Anthropic API key.
"""

import json
import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import av
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.util import sandbox
from inspect_swe import claude_code

from evals.identity.files import workspace_files
from evals.identity.prompt import prompt
from evals.identity.stubs import OUTPUT, build
from cell_tracking.hashing import hash_file
from cell_tracking.clips import clip_marks, clip_range, cut_clip
from cell_tracking.identity import IdentityMarks, evaluate

ROOT = Path(__file__).resolve().parents[2]
MARKS = ROOT / "data" / "eval" / "identity_marks.json"
VIDEO = ROOT / "data" / "timelapse1.avi"


CLAUDE_CODE_VERSION = "2.1.305"
CODEX_VERSION = "0.162.1"


def run_dir() -> Path:
    """Where this run's saved answers and transcripts go: the launcher's tracked runs/<id>/ folder (RUN_DIR),
    or the git-ignored runs/scratch for stubs and ad hoc runs."""
    return Path(os.environ.get("RUN_DIR") or ROOT / "runs" / "scratch")


@dataclass(frozen=True)
class Variant:
    """One sample: the video the agent gets, and the marks its output is scored against."""

    id: str
    video: Path
    video_name: str
    marks: IdentityMarks
    frame_count: int


def full_variant() -> Variant:
    with av.open(str(VIDEO)) as container:
        frame_count = container.streams.video[0].frames
    return Variant("full", VIDEO, VIDEO.name, IdentityMarks.model_validate_json(MARKS.read_text()), frame_count)


def clip_variants(groups: str | None, margin: int) -> list[Variant]:
    """A lossless clip around each marked group (plus margin frames), cached under .cache/clips."""
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
        # keyed by the source video's hash so a clip cut from another version of the video is never reused
        clip = ROOT / ".cache" / "clips" / f"{hash_file(VIDEO)[:12]}_{group.name}_m{margin}" / "clip.avi"
        if not clip.exists():
            cut_clip(VIDEO, first, last, clip)
        variants.append(Variant(group.name, clip, clip.name, clip_marks(marks, group.name, first, clip), last - first + 1))
    return variants


# Runs as root in the sandbox before the agent starts. Only the renderer is exposed; evaluation and
# checking code is never uploaded, and the agent user owns the workspace.
def setup(agent: str) -> str:
    # Match the host uid so the Codex process can read/write a mode-0600 bind-mounted auth file.
    uid = os.getuid() if agent == "codex_cli" and os.getuid() else 1000
    common = f"""
set -euo pipefail
cd /workspace
useradd --create-home --shell /bin/bash --uid {uid} agent
sed -i '/^cell-identity\\|^cell-eval-frames/d' pyproject.toml
printf '# Renderer workspace\\n' > README.md
pip install --quiet --no-cache-dir uv nodejs-wheel
UV_PROJECT_ENVIRONMENT=/workspace/.venv uv sync --locked --no-dev --group agent
mkdir -p output
chown -R agent:agent /workspace
"""
    if agent == "codex_cli":
        return common + f"""
npm install --global --silent @openai/codex@{CODEX_VERSION}
ln -sf "$(npm prefix -g)/bin/codex" /usr/local/bin/codex
install -d -o agent -g agent -m 700 /home/agent/.codex
ln -s /run/codex-auth.json /home/agent/.codex/auth.json
# Codex launches login shells; /etc/profile otherwise replaces the inherited virtualenv PATH.
printf 'export PATH="/workspace/.venv/bin:$PATH"\\n' > /etc/profile.d/agent-venv.sh
"""
    return common + f"""
npm install --global --silent @anthropic-ai/claude-code@{CLAUDE_CODE_VERSION}
ln -sf "$(npm prefix -g)/bin/claude" /usr/local/bin/claude
"""


@solver
def stub(mode: str, variants: dict[str, Variant]):
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        variant = variants[str(state.sample_id)]
        if mode == "invalid":
            text = '{"schema_version": 1}'
        else:
            text = build(variant.marks, mode=mode)
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
        if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            raise RuntimeError("Set CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`) to run agent=claude_cli")
        # The compose file passes the token into the container; passing it here would put it in Inspect's logs.
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
                                          env={"HOME": "/home/agent", "PATH": "/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin"},
                                          timeout=minutes * 60, timeout_retry=False)
            returncode = result.returncode
        except TimeoutError:
            pass
        stream, stderr = await read_or_empty("/tmp/claude_stream.jsonl"), await read_or_empty("/tmp/claude_stderr.txt")
        folder = run_dir() / "transcripts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%dT%H%M%S')}_{state.sample_id}_{model}_{effort or 'default'}.jsonl"
        path.write_text(stream)
        transcript().info({"returncode": returncode, "timed_out": returncode is None, "seconds": round(time.time() - started),
                           "stream": str(path), "stderr": stderr[-2000:]}, source="claude_cli")
        return state

    return solve


@solver
def codex_cli(model: str, effort: str | None, minutes: int):
    """Run native Codex with the auth file mounted by compose.codex.yaml, without an Inspect model proxy."""
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        command = [
            "codex", "exec", "--model", model, "--json", "--color", "never",
            "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-c", 'cli_auth_credentials_store="file"',
            "--output-last-message", "/tmp/codex_final.md",
        ]
        if effort:
            command += ["-c", f"model_reasoning_effort={json.dumps(effort)}"]
        command.append(state.input_text)
        shell = (
            "codex --version > /tmp/codex_version.txt; "
            f"exec {shlex.join(command)} > /tmp/codex_events.jsonl 2> /tmp/codex_stderr.txt"
        )
        folder = run_dir() / "transcripts" / f"codex_{uuid4().hex}"
        folder.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        returncode, timed_out = None, False
        try:
            result = await sandbox().exec(
                ["bash", "-c", shell], cwd="/workspace", user="root" if os.getuid() == 0 else "agent",
                env={"HOME": "/home/agent", "CODEX_HOME": "/home/agent/.codex",
                     "PATH": "/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin"},
                timeout=minutes * 60, timeout_retry=False,
            )
            returncode = result.returncode
        except TimeoutError:
            timed_out = True
        finally:
            for source, name in [("/tmp/codex_events.jsonl", "events.jsonl"),
                                 ("/tmp/codex_stderr.txt", "stderr.txt"), ("/tmp/codex_final.md", "final.md")]:
                (folder / name).write_text(await read_or_empty(source))
            # exec's event stream omits some native tool events, including image viewing.
            # Keep the native sessions too, without mounting any host conversations.
            native_error = None
            try:
                sessions = await sandbox().exec(
                    ["find", "/home/agent/.codex/sessions", "-type", "f", "-name", "*.jsonl"],
                    timeout=10, timeout_retry=False,
                )
                if sessions.returncode:
                    native_error = f"find exited with {sessions.returncode}"
                for source in sessions.stdout.splitlines():
                    (folder / ("session_" + Path(source).name)).write_text(await read_or_empty(source))
            except Exception as error:
                native_error = type(error).__name__
            status = {
                "agent": "codex_cli", "sample_id": str(state.sample_id), "model": model, "effort": effort,
                "version": (await read_or_empty("/tmp/codex_version.txt")).strip(),
                "returncode": returncode, "timed_out": timed_out,
                "seconds": round(time.monotonic() - started), "transcript": str(folder),
                "native_transcript_error": native_error,
            }
            (folder / "status.json").write_text(json.dumps(status, indent=2) + "\n")
            state.metadata["agent_status"] = status
            transcript().info(status, source="codex_cli")
        return state

    return solve


@scorer(metrics={"*": [mean()]})
def identity_scorer(variants: dict[str, Variant]):
    async def score(state: TaskState, target: Target) -> Score:
        try:
            text = await sandbox().read_file(OUTPUT)
        except FileNotFoundError:
            return failed("output/annotations.json was not written")
        saved = run_dir() / "outputs" / f"{time.strftime('%Y%m%dT%H%M%S')}_{state.sample_id}.annotations.json"
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(text)
        variant = variants[str(state.sample_id)]
        evaluation = evaluate(text, variant.marks, variant.frame_count)
        if not evaluation.valid:
            return failed(evaluation.reason or "invalid")
        covered = evaluation.marks_covered
        value = {
            "valid": 1.0,
            "same_cell": evaluation.same_cell.score,
            "different_cell": evaluation.different_cell.score,
            "marks_covered": covered.passed / covered.total,
            "mark_share": evaluation.mark_share,
            "all_pass": float(evaluation.all_pass),
        }
        metadata = evaluation.model_dump(mode="json") | {"saved_annotations": str(saved)}
        if "agent_status" in state.metadata:
            metadata["agent_status"] = state.metadata["agent_status"]
        return Score(value=value, explanation=evaluation.model_dump_json(exclude={"valid", "reason"}), metadata=metadata)

    return score


def failed(reason: str) -> Score:
    value = {"valid": 0.0, "same_cell": 0.0, "different_cell": 0.0, "marks_covered": 0.0, "mark_share": 0.0, "all_pass": 0.0}
    return Score(value=value, explanation=reason)


def build_task(variants: list[Variant], agent: str, model: str | None, effort: str | None, minutes: int,
               compose: str | None) -> Task:
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    model = model or ("gpt-6-luna" if agent == "codex_cli" else "haiku")
    by_id = {variant.id: variant for variant in variants}
    if agent == "claude_cli":
        solver_ = claude_cli(model, effort, minutes)
    elif agent == "codex_cli":
        from evals.identity.codex_run import auth_file

        auth_file()  # fail before creating containers if file-backed subscription auth is unavailable
        solver_ = codex_cli(model, effort, minutes)
    elif agent == "claude":
        solver_ = claude_code(cwd="/workspace", user="agent", effort=effort, permission_mode="bypassPermissions")
    elif agent.startswith("stub_"):
        solver_ = stub(agent.removeprefix("stub_"), by_id)
    else:
        raise ValueError(f"Unknown agent {agent!r}; use codex_cli, claude_cli, claude, stub_oracle, stub_empty or stub_invalid")
    needs_workspace = not agent.startswith("stub_")
    samples = [
        Sample(
            id=variant.id,
            input=prompt(variant.video_name),
            files={path: str(source) for path, source in workspace_files(variant.video, variant.video_name).items()} if needs_workspace else None,
            setup=setup(agent) if needs_workspace else None,
        )
        for variant in variants
    ]
    return Task(
        dataset=samples,
        solver=solver_,
        scorer=identity_scorer(by_id),
        sandbox=("docker", str(ROOT / (compose or (CODEX_COMPOSE if agent == "codex_cli" else COMPOSE)))),
        time_limit=(minutes + 5) * 60,  # setup and scoring happen inside the sample limit
    )


COMPOSE = str(Path(__file__).with_name("compose.yaml"))
CODEX_COMPOSE = str(Path(__file__).with_name("compose.codex.yaml"))


@task
def identity(agent: str = "claude_cli", model: str | None = None, effort: str | None = None, minutes: int = 120,
             compose: str | None = None) -> Task:
    return build_task([full_variant()], agent, model, effort, minutes, compose)


@task
def identity_clips(agent: str = "claude_cli", model: str | None = None, effort: str | None = None, minutes: int = 120,
                   groups: str | None = None, margin: int = 2, compose: str | None = None) -> Task:
    """Short clips around each marked group (all by default, or e.g. groups=24-32,66-72)."""
    return build_task(clip_variants(groups, margin), agent, model, effort, minutes, compose)
