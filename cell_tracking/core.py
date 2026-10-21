"""Shared pixel-run types and the base model for the saved records."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

# The json_schema_extra bounds only describe the published schema; validate_runs checks the real bounds.
type Run = tuple[
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 0})],
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 0})],
    Annotated[StrictInt, Field(json_schema_extra={"minimum": 1})],
]
type Mask = list[Run]

RUN_ENCODING = (
    "Lossless horizontal runs [y, x_start, x_end] with an exclusive x_end: [10, 20, 23] is exactly pixels "
    "(20, 10), (21, 10) and (22, 10). Runs have integer bounds, are sorted by row and then starting column, "
    "must not overlap within a mask, and touching runs are coalesced."
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Source(Record):
    """The video that was annotated."""

    path: Annotated[str, Field(min_length=1)]
    sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$", description="SHA-256 of the video file.")]
    width: Annotated[StrictInt, Field(gt=0, description="Decoded frame width in pixels.")]
    height: Annotated[StrictInt, Field(gt=0, description="Decoded frame height in pixels.")]


def validate_runs(mask: Mask, width: int, height: int, label: str) -> None:
    """Raise ValueError unless the runs are in bounds, sorted by row then column, disjoint and coalesced."""
    previous: Run | None = None
    for run in mask:
        y, start, end = run
        if not (0 <= y < height and 0 <= start < end <= width):
            raise ValueError(f"Out-of-bounds pixel run in {label}: {run}")
        if previous is not None:
            py, _, pend = previous
            if y < py or (y == py and start <= pend):
                raise ValueError(f"Runs must be sorted, disjoint and coalesced in {label}")
        previous = run


def mask_center(mask: Mask) -> tuple[float, float] | None:
    """Area-weighted centroid (x, y) of the pixels in the runs, or None for an empty mask."""
    area = sum(end - start for _, start, end in mask)
    if area == 0:
        return None
    return (
        sum((start + end - 1) * (end - start) / 2 for _, start, end in mask) / area,
        sum(y * (end - start) for y, start, end in mask) / area,
    )
