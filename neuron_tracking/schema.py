"""Generate the published JSON Schemas from the pydantic annotation model.

Run `uv run python -m neuron_tracking.schema` to rewrite both files, or add `--check` to fail when they differ.
"""

import copy
import json
import sys
from pathlib import Path

from neuron_tracking.annotations import Annotations

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "annotations.schema.json"
IDENTITY = ROOT / "tasks" / "identity" / "annotations.schema.json"

EXAMPLE = {
    "schema_version": 1,
    "revision": 1,
    "source": {"path": "synthetic_clip.avi", "sha256": "0" * 64, "width": 64, "height": 48},
    "frames": [{"frame_index": 0, "timestamp_s": 0.0}],
    "cells": [{"id": "N001", "color": "#e6194b"}],
    "observations": [
        {
            "cell_id": "N001",
            "frame_index": 0,
            "visibility": "visible",
            "body": [[10, 20, 27], [11, 20, 23]],
            "branches": [],
            "uncertain": [[10, 27, 28]],
            "review": "proposed",
        }
    ],
}


def strip_titles(node):
    if isinstance(node, dict):
        return {key: strip_titles(value) for key, value in node.items() if key != "title"}
    if isinstance(node, list):
        return [strip_titles(item) for item in node]
    return node


def shared_schema() -> dict:
    schema = strip_titles(Annotations.model_json_schema())
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Cell pixel annotations", **schema}


def identity_schema() -> dict:
    """The shared schema with guidance for the task that annotates whole cells, and an example."""
    schema = copy.deepcopy(shared_schema())
    schema["description"] = (
        "Pixel annotations of dark cells in a microscopy clip, saved as annotations.json. All pixel coordinates "
        "refer to the decoded source image: integer (x, y) is column x, row y, with (0, 0) at the top left. "
        "Frame indices start at zero. Keep one observation per cell per included frame, including explicit absence "
        "states. Render the saved file with the renderer named in the prompt. This schema checks structure only; "
        "separately validate run bounds (0 <= y < height, 0 <= x_start < x_end <= width), that the masks of one "
        "observation do not overlap, unique cell/frame observations, complete frame coverage, and the references "
        "between frames, cell ids and observations. A schema-valid file can still contain wrong masks."
    )
    properties = schema["properties"]
    properties["frames"]["description"] = (
        "Every source frame, in order: frame_index starts at zero and timestamp_s is the frame's presentation "
        "time in the source, strictly increasing."
    )
    properties["cells"]["description"] = (
        "One entry per cell identity. Each id is persistent across all frames, and each color is distinct and is "
        "used to render that cell."
    )
    properties["observations"]["description"] = (
        "One observation per cell per included frame, including frames where the cell is absent. Masks of "
        "different cells are independent, so ambiguous ownership can stay uncertain instead of being forced onto "
        "one cell."
    )
    observation = schema["$defs"]["Observation"]["properties"]
    observation["body"]["description"] = (
        "Every pixel you can attribute to this cell in this frame, soma and any attached processes together. "
        "There is no body/branch distinction in this task."
    )
    observation["branches"]["description"] = (
        "Always [] in this task. The field stays because the shared schema and renderer require it."
    )
    observation["uncertain"]["description"] = (
        "Optional candidate pixels whose ownership you cannot resolve. They are excluded from body and must be "
        "reported as unresolved in your final response."
    )
    schema["examples"] = [EXAMPLE]
    return schema


def render(schema: dict) -> str:
    return json.dumps(schema, indent=2) + "\n"


def main() -> None:
    outputs = {SHARED: render(shared_schema()), IDENTITY: render(identity_schema())}
    if "--check" in sys.argv:
        stale = [str(path.relative_to(ROOT)) for path, text in outputs.items() if path.read_text() != text]
        if stale:
            raise SystemExit(f"Out of date, run `uv run python -m neuron_tracking.schema`: {stale}")
        return
    for path, text in outputs.items():
        path.write_text(text)


if __name__ == "__main__":
    main()
