"""Pixel annotation models and image-dependent validation."""

import json
from collections.abc import Iterator
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

# The json_schema_extra bounds only describe the published schema; the model validator checks run bounds.
type Run = tuple[
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 0})],
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 0})],
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 1})],
]
type Mask = Annotated[
    list[Run],
    Field(
        description=(
            "Lossless horizontal runs [y, x_start, x_end] with an exclusive x_end: [10, 20, 23] is exactly pixels "
            "(20, 10), (21, 10) and (22, 10). Runs have integer bounds, are sorted by row and then starting column, "
            "must not overlap within a mask, and touching runs are coalesced. An empty mask is []."
        )
    ),
]


def mask_center(mask: Mask) -> tuple[float, float] | None:
    area = sum(end - start for _, start, end in mask)
    if area == 0:
        return None
    return (
        sum((start + end - 1) * (end - start) / 2 for _, start, end in mask) / area,
        sum(y * (end - start) for y, start, end in mask) / area,
    )


class Part(StrEnum):
    BODY = "body"
    BRANCHES = "branches"
    UNCERTAIN = "uncertain"


class Visibility(StrEnum):
    VISIBLE = "visible"
    UNCERTAIN = "uncertain"
    NOT_VISIBLE = "not_visible"
    OUT_OF_FRAME = "out_of_frame"


class Review(StrEnum):
    PROPOSED = "proposed"
    AGENT_REVIEWED = "agent_reviewed"
    HUMAN_REVIEWED = "human_reviewed"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Source(Record):
    """The video that was annotated."""

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$", description="SHA-256 of the video file.")]
    width: Annotated[StrictInt, Field(gt=0, description="Decoded frame width in pixels.")]
    height: Annotated[StrictInt, Field(gt=0, description="Decoded frame height in pixels.")]


class Frame(Record):
    frame_index: Annotated[StrictInt, Field(ge=0, description="Index in decode order, starting at zero.")]
    timestamp_s: Annotated[float, Field(description="Presentation time in seconds; strictly increasing across frames.")]


class CellIdentity(Record):
    id: Annotated[str, Field(min_length=1, description="Persistent across all frames.")]
    color: Annotated[str, Field(pattern="^#[0-9a-fA-F]{6}$", description="Distinct per cell; used to render it.")]


class Observation(Record):
    """One cell in one frame."""

    cell_id: Annotated[str, Field(description="The id of the cell in `cells`.")]
    frame_index: Annotated[StrictInt, Field(ge=0)]
    visibility: Annotated[
        Visibility,
        Field(
            description=(
                "Describes the observation as a whole. not_visible and out_of_frame observations have empty masks; "
                "the uncertain mask describes specific ambiguous pixels even when other parts are visible."
            )
        ),
    ]
    body: Annotated[Mask, Field(description="Pixels of the cell body (soma).")]
    branches: Annotated[Mask, Field(description="Pixels of its visible processes, including their full width and tips.")]
    uncertain: Annotated[
        Mask,
        Field(
            description=(
                "Candidate pixels whose ownership or body/branch classification cannot be resolved. They are "
                "excluded from body and branches and must be reported as unresolved."
            )
        ),
    ]
    review: Review

    def iter_masks(self) -> Iterator[tuple[Part, Mask]]:
        yield Part.BODY, self.body
        yield Part.BRANCHES, self.branches
        yield Part.UNCERTAIN, self.uncertain


class Annotations(Record):
    """Pixel masks of cells in a microscopy clip, saved as annotations.json."""

    schema_version: Annotated[StrictInt, Field(ge=1, le=1)]
    revision: Annotated[StrictInt, Field(ge=1, description="Starts at 1; increase it when you save a changed annotation.")]
    source: Source
    frames: Annotated[
        list[Frame],
        Field(min_length=1, description="Every included source frame, in order, with its presentation time."),
    ]
    cells: Annotated[list[CellIdentity], Field(description="One entry per cell identity.")]
    observations: Annotated[
        list[Observation],
        Field(description="One observation per cell per included frame, including frames where the cell is absent."),
    ]

    @model_validator(mode="after")
    def validate_masks_and_references(self) -> Self:
        indices = [frame.frame_index for frame in self.frames]
        if indices != sorted(set(indices)):
            raise ValueError("Frame indices must be unique and sorted")
        times = [frame.timestamp_s for frame in self.frames]
        if any(right <= left for left, right in pairwise(times)):
            raise ValueError("Source timestamps must strictly increase")
        ids = {cell.id for cell in self.cells}
        if len(ids) != len(self.cells):
            raise ValueError("Duplicate neuron ID")
        if len({cell.color.lower() for cell in self.cells}) != len(ids):
            raise ValueError("Cell colors must be distinct")
        frames = set(indices)
        pairs: set[tuple[str, int]] = set()
        for observation in self.observations:
            pair = observation.cell_id, observation.frame_index
            if pair in pairs or pair[0] not in ids or pair[1] not in frames:
                raise ValueError(f"Duplicate or unreferenced observation: {pair}")
            pairs.add(pair)
            intervals: list[Run] = []
            for part, mask in observation.iter_masks():
                previous: Run | None = None
                for run in mask:
                    y, start, end = run
                    if not (0 <= y < self.source.height and 0 <= start < end <= self.source.width):
                        raise ValueError(f"Out-of-bounds pixel run in {pair}, {part}: {run}")
                    if previous is not None:
                        py, _, pend = previous
                        if y < py or (y == py and start <= pend):
                            raise ValueError(f"Runs must be sorted, disjoint and coalesced in {pair}, {part}")
                    previous = run
                intervals.extend(mask)
            intervals.sort()
            for left, right in pairwise(intervals):
                if left[0] == right[0] and right[1] < left[2]:
                    raise ValueError(f"Body, branches and uncertainty overlap in {pair}")
            if observation.visibility in (Visibility.NOT_VISIBLE, Visibility.OUT_OF_FRAME) and intervals:
                raise ValueError(f"Absent observation has pixels: {pair}")
        if len(pairs) != len(ids) * len(frames):
            raise ValueError("Need one observation per neuron per included frame")
        return self


def parse_annotations(raw: str | bytes) -> Annotations:
    """Parse annotation JSON; files saved before the format said cells (neurons, neuron_id) are accepted."""
    document = json.loads(raw)
    if isinstance(document, dict) and "neurons" in document and "cells" not in document:
        document = {("cells" if key == "neurons" else key): value for key, value in document.items()}
        document["observations"] = [
            {("cell_id" if key == "neuron_id" else key): value for key, value in row.items()} if isinstance(row, dict) else row
            for row in document.get("observations", [])
        ]
        raw = json.dumps(document)
    return Annotations.model_validate_json(raw)
