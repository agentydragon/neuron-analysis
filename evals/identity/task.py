"""Inspect task: annotate neuron identities in the sample clip, scored against painted identity marks.

Run from the repository root, for example:
    uv run --group evals inspect eval evals/identity/task.py -T agent=stub_oracle
    uv run --group evals inspect eval evals/identity/task.py --model anthropic/claude-haiku-5-5 -T effort=xhigh
"""

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
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
def identity(agent: str = "claude", effort: str | None = None, minutes: int = 30) -> Task:
    if agent == "claude":
        solver_ = claude_code(cwd="/workspace", user="agent", effort=effort, permission_mode="bypassPermissions")
    elif agent.startswith("stub_"):
        solver_ = stub(agent.removeprefix("stub_"))
    else:
        raise ValueError(f"Unknown agent {agent!r}; use claude, stub_oracle, stub_empty or stub_invalid")
    return Task(
        dataset=[Sample(input=PROMPT)],
        solver=solver_,
        scorer=identity_scorer(),
        sandbox=("docker", str(Path(__file__).with_name("compose.yaml"))),
        time_limit=minutes * 60,
    )
