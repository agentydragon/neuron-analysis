"""Stub 'agents' that write a fixed annotations.json, to exercise the pipeline without a model."""

from cell_tracking.identity import IdentityMarks
from cell_tracking.masks import CellMask, CellMasks

OUTPUT = "/workspace/output/annotations.json"


def build(marks: IdentityMarks, *, mode: str) -> str:
    """Return annotation JSON: 'oracle' reproduces the marks, 'empty' is valid with no cells."""
    entries = []
    if mode == "oracle":
        cells = [cell for group in marks.groups for cell in group.cells]
        for number, cell in enumerate(cells):
            entries += [CellMask(cell=f"N{number:03d}", frame=mark.frame_index, mask=mark.pixels) for mark in cell.marks]
    return CellMasks(masks=entries).model_dump_json()
