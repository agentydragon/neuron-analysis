import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tasks" / "identity" / "run.sh"


def stage(tmp_path, name="trial"):
    env = {"PATH": "/usr/bin:/bin", "RUNS_DIR": str(tmp_path)}
    return subprocess.run([SCRIPT, name, "--stage-only"], env=env, capture_output=True, text=True)


def test_staged_workspace_has_inputs_and_no_evaluation_data(tmp_path):
    result = stage(tmp_path)
    assert result.returncode == 0, result.stderr
    workspace = Path(result.stdout.strip())
    assert workspace == tmp_path / "identity_trial" / "workspace"
    for name in ("annotate.md", "target.md", "annotations.schema.json", "target.jpg", "IMG_6128.AVI", "pyproject.toml", "uv.lock"):
        assert (workspace / name).is_file()
    assert (workspace / "output").is_dir()
    staged = {path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file()}
    assert not [path for path in staged if path.startswith(("data/", "tests/", "debug/")) or "sample_checks" in path]
    assert {path for path in staged if path.startswith("neuron_tracking/")} == {
        "neuron_tracking/annotations.py",
        "neuron_tracking/render.py",
    }
    pyproject = (workspace / "pyproject.toml").read_text()
    assert "neuron-render" in pyproject and "neuron-check" not in pyproject and "neuron-identity" not in pyproject
    assert "identity_marks" not in "".join(path.read_text(errors="ignore") for path in workspace.glob("*.md"))


def test_refuses_existing_run(tmp_path):
    assert stage(tmp_path).returncode == 0
    again = stage(tmp_path)
    assert again.returncode == 1
    assert "already exists" in again.stderr


@pytest.mark.parametrize("prompt", ["annotate.md", "target.md"])
def test_prompt_files_do_not_mention_evaluation_locations(prompt):
    text = (ROOT / "tasks" / "identity" / prompt).read_text()
    assert "data/eval" not in text and "identity_marks" not in text


def test_only_annotations_json_is_requested():
    from evals.identity.prompt import PROMPT

    launch = [PROMPT, SCRIPT.read_text()]
    assert all("output/annotations.json" in text and "review record" not in text and "annotated AVI" not in text for text in launch)
    prompt = (ROOT / "tasks" / "identity" / "annotate.md").read_text()
    assert "output/annotations.json" in prompt and "review.json" not in prompt and "annotated.avi" not in prompt


def test_claude_code_web_launcher_and_compose_stay_consistent():
    import re
    import subprocess as sp

    folder = ROOT / "evals" / "identity"
    assert sp.run(["bash", "-n", str(folder / "run-claude-code-web.sh")]).returncode == 0
    image = lambda name: re.search(r"^\s*image: (\S+)", (folder / name).read_text(), re.M).group(1)
    assert image("compose.yaml") == image("compose.claude-code-web.yaml")


def test_agent_facing_prompt_does_not_call_the_cells_neurons():
    import re

    from evals.identity.prompt import PROMPT

    launch_line = next(line for line in SCRIPT.read_text().splitlines() if "Read annotate.md" in line)
    text = (ROOT / "tasks" / "identity" / "annotate.md").read_text() + PROMPT + launch_line
    assert not re.search(r"neuron(?!-render)", text, re.I)


def strip_guidance(node):
    if isinstance(node, dict):
        return {key: strip_guidance(value) for key, value in node.items() if key not in ("description", "examples", "title")}
    if isinstance(node, list):
        return [strip_guidance(item) for item in node]
    return node


def test_identity_schema_is_the_shared_schema_plus_guidance():
    import json

    import jsonschema

    shared = json.loads((ROOT / "annotations.schema.json").read_text())
    identity = json.loads((ROOT / "tasks" / "identity" / "annotations.schema.json").read_text())
    assert strip_guidance(identity) == strip_guidance(shared)
    validator = jsonschema.Draft202012Validator(identity)
    for example in identity["examples"]:
        validator.validate(example)
