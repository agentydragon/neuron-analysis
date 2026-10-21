"""The JSON Schema for the identity task's whole-cell masks, derived from the pydantic model; never committed.

    uv run python -m cell_tracking.schema [--output FILE]
"""

import argparse
import json
from pathlib import Path

from cell_tracking.masks import CellMasks


def schema() -> dict:
    return CellMasks.model_json_schema()


def render() -> str:
    return json.dumps(schema(), indent=2) + "\n"


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render())
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write here instead of printing")
    arguments = parser.parse_args()
    if arguments.output:
        write(arguments.output)
    else:
        print(render(), end="")


if __name__ == "__main__":
    main()
