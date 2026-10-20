"""Stub 'agents' that write a fixed annotations.json, to exercise the pipeline without a model."""

import colorsys
import json
from pathlib import Path

import av

from neuron_tracking.identity import IdentityMarks

OUTPUT = "/workspace/output/annotations.json"


def source_frames(video: Path) -> list[dict]:
    with av.open(str(video)) as container:
        return [{"frame_index": i, "timestamp_s": float(frame.time)} for i, frame in enumerate(container.decode(video=0))]


def build(marks: IdentityMarks, video: Path, *, mode: str) -> str:
    """Return annotation JSON: 'oracle' reproduces the marks, 'empty' is valid with nothing visible."""
    frames = source_frames(video)
    cells = [(group.name, cell) for group in marks.groups for cell in group.cells] if mode == "oracle" else []
    if not cells:
        cells = [("none", None)]
    neurons, observations = [], []
    for number, (group, cell) in enumerate(cells):
        red, green, blue = colorsys.hsv_to_rgb(number / len(cells), 0.9, 0.95)
        identity = f"N{number:03d}"
        neurons.append({"id": identity, "color": "#%02x%02x%02x" % (round(red * 255), round(green * 255), round(blue * 255))})
        runs = {mark.frame_index: mark.pixels for mark in cell.marks} if cell else {}
        for frame in frames:
            body = [list(run) for run in runs.get(frame["frame_index"], [])]
            observations.append(
                {
                    "neuron_id": identity,
                    "frame_index": frame["frame_index"],
                    "visibility": "visible" if body else "not_visible",
                    "body": body,
                    "branches": [],
                    "uncertain": [],
                    "review": "proposed",
                }
            )
    source = marks.source
    return json.dumps(
        {
            "schema_version": 1,
            "revision": 1,
            "source": {"path": source.path, "sha256": source.sha256, "width": source.width, "height": source.height},
            "frames": frames,
            "neurons": neurons,
            "observations": observations,
        }
    )
