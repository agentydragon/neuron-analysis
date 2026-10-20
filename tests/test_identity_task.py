import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tasks" / "identity" / "run.sh"


def stage(tmp_path, name="trial"):
    env = {"PATH": "/usr/bin:/bin", "NEURON_RUNS": str(tmp_path)}
    return subprocess.run([SCRIPT, name, "--stage-only"], env=env, capture_output=True, text=True)


def test_staged_workspace_has_inputs_and_no_evaluation_data(tmp_path):
    result = stage(tmp_path)
    assert result.returncode == 0, result.stderr
    workspace = Path(result.stdout.strip())
    assert workspace == tmp_path / "identity_trial" / "workspace"
    for name in ("annotate.md", "format.md", "annotations.schema.json", "IMG_6128.AVI", "pyproject.toml", "uv.lock"):
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


@pytest.mark.parametrize("prompt", ["annotate.md", "format.md"])
def test_prompt_files_do_not_mention_evaluation_locations(prompt):
    text = (ROOT / "tasks" / "identity" / prompt).read_text()
    assert "data/eval" not in text and "identity_marks" not in text


def test_only_annotations_json_is_requested():
    from evals.identity.task import PROMPT

    launch = [PROMPT, SCRIPT.read_text()]
    assert all("output/annotations.json" in text and "review record" not in text and "annotated AVI" not in text for text in launch)
    prompt = (ROOT / "tasks" / "identity" / "annotate.md").read_text()
    assert "output/annotations.json" in prompt and "review.json" not in prompt and "annotated.avi" not in prompt
