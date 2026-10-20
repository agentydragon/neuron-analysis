"""JSON Schemas derived from the pydantic models when needed; none is committed.

    uv run python -m cell_tracking.schema cells [--output FILE]   # the identity task's whole-cell masks
    uv run python -m cell_tracking.schema full [--output FILE]    # the full annotation format
"""

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from cell_tracking.annotations import Annotations
from cell_tracking.masks import CellMasks

MODELS: dict[str, type[BaseModel]] = {"cells": CellMasks, "full": Annotations}


def schema_for(kind: str) -> dict:
    return MODELS[kind].model_json_schema()


def render(kind: str) -> str:
    return json.dumps(schema_for(kind), indent=2) + "\n"


def write(kind: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(kind))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(MODELS))
    parser.add_argument("--output", type=Path, help="Write here instead of printing")
    arguments = parser.parse_args()
    if arguments.output:
        write(arguments.kind, arguments.output)
    else:
        print(render(arguments.kind), end="")


if __name__ == "__main__":
    main()
