"""The files uploaded into an agent's workspace; kept free of Inspect imports so tests can inspect them."""

from pathlib import Path

from cell_tracking.schema import write

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_CACHE = ROOT / "runs" / "schema" / "annotations.schema.json"


def workspace_files(video: Path, video_name: str) -> dict[str, Path]:
    """Source paths by destination; the schema is derived from the model into a cache file each time."""
    return {
        "/workspace/annotate.md": ROOT / "tasks/identity/annotate.md",
        "/workspace/target.md": ROOT / "tasks/identity/target.md",
        "/workspace/annotations.schema.json": write("cells", SCHEMA_CACHE),
        f"/workspace/{video_name}": video,
        "/workspace/target.jpg": ROOT / "data/photo_2026-10-19_14-30-28.jpg",
        "/workspace/pyproject.toml": ROOT / "pyproject.toml",
        "/workspace/uv.lock": ROOT / "uv.lock",
        "/workspace/.python-version": ROOT / ".python-version",
        "/workspace/cell_tracking/annotations.py": ROOT / "cell_tracking/annotations.py",
        "/workspace/cell_tracking/hashing.py": ROOT / "cell_tracking/hashing.py",
        "/workspace/cell_tracking/masks.py": ROOT / "cell_tracking/masks.py",
        "/workspace/cell_tracking/render.py": ROOT / "cell_tracking/render.py",
    }
