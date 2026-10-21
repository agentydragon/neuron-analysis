"""The files uploaded into an agent's workspace; kept free of Inspect imports so tests can inspect them."""

from pathlib import Path

from cell_tracking.schema import write

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_CACHE = ROOT / ".cache" / "schema" / "annotations.schema.json"


def workspace_files(video: Path, video_name: str) -> dict[str, Path]:
    """Source paths by destination; the schema is derived from the model into a cache file each time.

    Every source must exist: Inspect treats an upload value that is not an existing path as the file's literal
    contents, so a missing source would silently give the agent a file containing just its path.
    """
    files = {
        "/workspace/annotate.md": ROOT / "tasks/identity/annotate.md",
        "/workspace/target.md": ROOT / "tasks/identity/target.md",
        "/workspace/annotations.schema.json": write(SCHEMA_CACHE),
        f"/workspace/{video_name}": video,
        "/workspace/target.jpg": ROOT / "data/photo_2026-10-19_14-30-28.jpg",
        "/workspace/pyproject.toml": ROOT / "pyproject.toml",
        "/workspace/uv.lock": ROOT / "uv.lock",
        "/workspace/.python-version": ROOT / ".python-version",
        "/workspace/cell_tracking/core.py": ROOT / "cell_tracking/core.py",
        "/workspace/cell_tracking/hashing.py": ROOT / "cell_tracking/hashing.py",
        "/workspace/cell_tracking/masks.py": ROOT / "cell_tracking/masks.py",
        "/workspace/cell_tracking/render.py": ROOT / "cell_tracking/render.py",
    }
    missing = [destination for destination, source in files.items() if not source.exists()]
    if missing:
        raise FileNotFoundError(f"Upload sources do not exist for {missing}")
    return files
