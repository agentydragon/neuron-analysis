"""Whole-cell masks: the identity task's output format, with a loader that lets the renderer read it."""

import colorsys
from pathlib import Path
from typing import Annotated, Self

import av
from pydantic import ConfigDict, Discriminator, Field, StrictInt, Tag, TypeAdapter, model_validator

from cell_tracking.annotations import (
    Annotations,
    CellIdentity,
    Frame,
    Observation,
    Record,
    RUN_ENCODING,
    Run,
    Source,
    Visibility,
    validate_runs,
)
from cell_tracking.hashing import hash_file


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


def color_for(index: int, total: int) -> str:
    """A stable, well-spread color for the index-th of total cells, so the agent never has to pick colors."""
    red, green, blue = colorsys.hsv_to_rgb(index / max(total, 1), 0.85, 0.95)
    return "#%02x%02x%02x" % (round(red * 255), round(green * 255), round(blue * 255))


def to_annotations(masks: CellMasks, source: Source, frames: list[Frame]) -> Annotations:
    """The full format for rendering: ids sorted, colors assigned, absent frames marked not visible."""
    ids = sorted({entry.cell for entry in masks.masks})
    by_key = {(entry.cell, entry.frame): entry.mask for entry in masks.masks}
    cells = [CellIdentity(id=identity, color=color_for(index, len(ids))) for index, identity in enumerate(ids)]
    observations = [
        Observation(
            cell_id=identity,
            frame_index=frame.frame_index,
            visibility=Visibility.VISIBLE if (identity, frame.frame_index) in by_key else Visibility.NOT_VISIBLE,
            body=by_key.get((identity, frame.frame_index), []),
            branches=[],
            uncertain=[],
        )
        for identity in ids
        for frame in frames
    ]
    return Annotations(schema_version=1, revision=1, source=source, frames=frames, cells=cells, observations=observations)


def probe_video(video: Path) -> tuple[list[Frame], int, int]:
    with av.open(str(video)) as container:
        decoded = list(container.decode(video=0))
    frames = [Frame(frame_index=index, timestamp_s=float(frame.time)) for index, frame in enumerate(decoded)]
    return frames, decoded[0].width, decoded[0].height


def _format(value: object) -> str:
    return "masks" if isinstance(value, dict) and "masks" in value else "full"


RENDERABLE = TypeAdapter(
    Annotated[Annotated[CellMasks, Tag("masks")] | Annotated[Annotations, Tag("full")], Discriminator(_format)]
)


def load_annotations(raw: str | bytes, video: Path) -> Annotations:
    """Read either format for rendering. Whole-cell masks borrow dimensions and timing from the video."""
    parsed = RENDERABLE.validate_json(raw)
    if isinstance(parsed, Annotations):
        return parsed
    frames, width, height = probe_video(video)
    parsed.check_bounds(width, height, len(frames))
    source = Source(path=video.name, sha256=hash_file(video), width=width, height=height)
    return to_annotations(parsed, source, frames)
