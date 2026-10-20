"""Read annotation files in any format we have used, including earlier field names (host-side only).

`python -m cell_tracking.legacy OLD.json NEW.json` rewrites a full-format file saved with the earlier field
names in the current format.
"""

import sys
from pathlib import Path
from typing import Annotated

from pydantic import Discriminator, Field, Tag, TypeAdapter

from cell_tracking.annotations import Annotations, CellIdentity, Observation
from cell_tracking.masks import CellMasks


class LegacyObservation(Observation):
    cell_id: Annotated[str, Field(validation_alias="neuron_id")]


class LegacyAnnotations(Annotations):
    """The full format as saved before it said cells: `neurons` and `neuron_id`."""

    cells: Annotated[list[CellIdentity], Field(validation_alias="neurons")]
    observations: list[LegacyObservation]


def _format(value: object) -> str:
    if isinstance(value, dict):
        if "masks" in value:
            return "masks"
        if "neurons" in value:
            return "legacy"
    return "full"


ANY_FORMAT = TypeAdapter(
    Annotated[
        Annotated[CellMasks, Tag("masks")] | Annotated[Annotations, Tag("full")] | Annotated[LegacyAnnotations, Tag("legacy")],
        Discriminator(_format),
    ]
)


def parse_any(raw: str | bytes) -> CellMasks | Annotations:
    """Whole-cell masks or full-format annotations, with earlier field names converted to the current ones."""
    parsed = ANY_FORMAT.validate_json(raw)
    if isinstance(parsed, LegacyAnnotations):
        return Annotations.model_validate_json(parsed.model_dump_json())
    return parsed


def parse_annotations(raw: str | bytes) -> Annotations:
    parsed = parse_any(raw)
    if isinstance(parsed, CellMasks):
        raise ValueError("Expected full-format annotations, got whole-cell masks")
    return parsed


def main() -> None:
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    target.write_text(parse_annotations(source.read_text()).model_dump_json(indent=1) + "\n")


if __name__ == "__main__":
    main()
