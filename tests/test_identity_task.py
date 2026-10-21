import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tasks" / "identity" / "run.sh"


def stage(tmp_path, name="trial"):
    env = {**os.environ, "RUNS_DIR": str(tmp_path / "runs"), "CACHE_DIR": str(tmp_path / "cache")}
    return subprocess.run([SCRIPT, name, "--stage-only"], env=env, capture_output=True, text=True)


def test_staged_workspace_has_inputs_and_no_evaluation_data(tmp_path):
    result = stage(tmp_path)
    assert result.returncode == 0, result.stderr
    workspace = Path(result.stdout.strip())
    assert workspace == tmp_path / "cache" / "workspaces" / "identity_trial"
    for name in ("annotate.md", "target.md", "annotations.schema.json", "target.jpg", "timelapse1.avi", "source.txt", "pyproject.toml", "uv.lock"):
        assert (workspace / name).is_file()
    assert (workspace / "output").is_dir()
    staged = {path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file()}
    assert not [path for path in staged if path.startswith(("data/", "tests/", "debug/")) or "sample_checks" in path]
    assert {path for path in staged if path.startswith("cell_tracking/")} == {
        "cell_tracking/core.py",
        "cell_tracking/hashing.py",
        "cell_tracking/masks.py",
        "cell_tracking/render.py",
        "cell_tracking/views.py",
    }
    pyproject = (workspace / "pyproject.toml").read_text()
    assert "cell-render" in pyproject and "cell-check" not in pyproject and "cell-identity" not in pyproject
    assert "identity_marks" not in "".join(path.read_text(errors="ignore") for path in workspace.glob("*.md"))
    assert (workspace / "source.txt").read_text().strip() == "timelapse1.avi"
    assert "cell-views" in pyproject


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


def test_nothing_in_the_staged_workspace_says_neuron():
    import tempfile

    from evals.identity.prompt import PROMPT

    result = stage(Path(tempfile.mkdtemp()), "wording")
    assert result.returncode == 0, result.stderr
    workspace = Path(result.stdout.strip())
    scanned = 0
    for path in workspace.rglob("*"):
        if path.is_file() and path.suffix.lower() not in (".avi", ".jpg") and ".venv" not in path.parts:
            assert "neuron" not in path.read_text(errors="ignore").lower(), path.relative_to(workspace)
            assert "neuron" not in path.name.lower()
            scanned += 1
    assert scanned >= 8
    assert "python -m evals.identity.prompt" in SCRIPT.read_text()
    assert "neuron" not in PROMPT.lower()


def test_inspect_uploads_do_not_say_neuron():
    from evals.identity.files import ROOT as repo
    from evals.identity.files import workspace_files

    for destination, source in workspace_files(repo / "data" / "timelapse1.avi", "timelapse1.avi").items():
        if Path(source).suffix.lower() not in (".avi", ".jpg"):
            assert "neuron" not in Path(source).read_text().lower(), destination
        assert "neuron" not in destination.lower()


def test_a_missing_upload_source_is_an_error_not_a_file_containing_its_path(tmp_path):
    from evals.identity.files import workspace_files

    with pytest.raises(FileNotFoundError, match="clip.avi"):
        workspace_files(tmp_path / "does-not-exist.avi", "clip.avi")
