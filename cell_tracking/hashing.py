"""File hashing shared by the renderer, mask loader and evaluation code."""

import hashlib
from pathlib import Path


def hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
