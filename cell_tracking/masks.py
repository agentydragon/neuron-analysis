"""Whole-cell masks: the identity task's output format."""

import colorsys
from pathlib import Path
from typing import Annotated, Self

import av
from pydantic import ConfigDict, Field, StrictInt, model_validator

from cell_tracking.core import RUN_ENCODING, Record, Run, validate_runs

EXAMPLE = {
    "masks": [
        {"cell": "A", "frame": 0, "mask": [[10, 20, 27], [11, 20, 23]]},
        {"cell": "A", "frame": 1, "mask": [[12, 22, 29], [13, 22, 25]]},
        {"cell": "B", "frame": 0, "mask": [[30, 5, 9]]},
    ]
}


class CellMask(Record):
    cell: Annotated[str, Field(min_length=1, description="Id of the cell. Use the same id for the same cell in every frame.")]
    frame: Annotated[StrictInt, Field(ge=0, description="Frame index in decode order, starting at zero.")]
    mask: Annotated[
        list[Run],
        Field(
            min_length=1,
            description=RUN_ENCODING + " A mask is never empty: omit the entry for a frame where the cell is not visible.",
        ),
    ]


class CellMasks(Record):
    """Pixel masks of dark cells in a microscopy clip, saved as annotations.json.

    Pixel coordinates refer to the decoded video image: integer (x, y) is column x, row y, with (0, 0) at the
    top left, and frame indices start at zero. Give each cell one id and keep it for that cell in every frame.
    A cell that is not visible in a frame has no entry for that frame. This schema checks structure only;
    separately check that run bounds are inside the image (0 <= y < height, 0 <= x_start < x_end <= width),
    that frame indices are within the video, and that no cell id repeats within a frame. A schema-valid file
    can still contain wrong masks.
    """

    model_config = ConfigDict(json_schema_extra={"examples": [EXAMPLE]})

    masks: Annotated[
        list[CellMask],
        Field(
            description=(
                "One entry per cell per frame in which the cell is visible. A frame without an entry for a cell "
                "means that cell is not visible there. Each cell id may appear at most once per frame."
            )
        ),
    ]

    @model_validator(mode="after")
    def validate_entries(self) -> Self:
        seen: set[tuple[str, int]] = set()
        for entry in self.masks:
            key = entry.cell, entry.frame
            if key in seen:
                raise ValueError(f"Duplicate entry for cell {entry.cell!r} in frame {entry.frame}")
            seen.add(key)
        return self

    def check_bounds(self, width: int, height: int, frame_count: int | None = None) -> None:
        """Raise ValueError unless every run is inside the image and sorted, disjoint and coalesced."""
        for entry in self.masks:
            if frame_count is not None and entry.frame >= frame_count:
                raise ValueError(f"Frame {entry.frame} is past the end of the video ({frame_count} frames)")
            validate_runs(entry.mask, width, height, f"cell {entry.cell!r}, frame {entry.frame}")

    def colors(self) -> dict[str, str]:
        """A stable, well-spread display color per cell (ids sorted), so the agent never has to pick colors."""
        ids = sorted({entry.cell for entry in self.masks})
        return {identity: color_for(index, len(ids)) for index, identity in enumerate(ids)}


def color_for(index: int, total: int) -> str:
    red, green, blue = colorsys.hsv_to_rgb(index / max(total, 1), 0.85, 0.95)
    return "#%02x%02x%02x" % (round(red * 255), round(green * 255), round(blue * 255))


class VideoInfo(Record):
    """Decoded size and presentation time of every frame of a video."""

    width: Annotated[StrictInt, Field(gt=0)]
    height: Annotated[StrictInt, Field(gt=0)]
    timestamps_s: Annotated[list[float], Field(min_length=1, description="Frame i is at timestamps_s[i].")]

    @classmethod
    def probe(cls, video: Path) -> Self:
        with av.open(str(video)) as container:
            frames = list(container.decode(video=0))
        if not frames:
            raise ValueError("Source contains no video frames")
        return cls(width=frames[0].width, height=frames[0].height, timestamps_s=[float(frame.time) for frame in frames])
