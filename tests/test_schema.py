import json

import jsonschema
import pytest

from cell_tracking.annotations import Annotations
from cell_tracking.masks import EXAMPLE, CellMasks
from cell_tracking.schema import MODELS, render, schema_for, write

FULL_EXAMPLE = {
    "schema_version": 1,
    "revision": 1,
    "source": {"path": "clip.avi", "sha256": "0" * 64, "width": 64, "height": 48},
    "frames": [{"frame_index": 0, "timestamp_s": 0.0}],
    "cells": [{"id": "N001", "color": "#e6194b"}],
    "observations": [
        {
            "cell_id": "N001",
            "frame_index": 0,
            "visibility": "visible",
            "body": [[10, 20, 27]],
            "branches": [],
            "uncertain": [],
            "review": "proposed",
        }
    ],
}


def test_schemas_are_derived_from_the_models_and_carry_their_guidance():
    cells = schema_for("cells")
    assert "no entry for that frame" in cells["description"]
    assert cells["examples"] == [EXAMPLE]
    assert cells["$defs"]["CellMask"]["properties"]["mask"]["minItems"] == 1
    assert "exclusive x_end" in cells["$defs"]["CellMask"]["properties"]["mask"]["description"]
    assert render("cells") == json.dumps(cells, indent=2) + "\n"


def test_examples_are_valid_under_their_schema_and_model():
    Annotations.model_validate_json(json.dumps(FULL_EXAMPLE))
    jsonschema.Draft202012Validator(schema_for("full")).validate(FULL_EXAMPLE)
    CellMasks.model_validate_json(json.dumps(EXAMPLE))
    jsonschema.Draft202012Validator(schema_for("cells")).validate(EXAMPLE)


def test_neither_schema_uses_the_word_neuron():
    assert all("neuron" not in render(kind).lower() for kind in MODELS)


@pytest.mark.parametrize(
    "broken",
    [
        {"masks": [{"cell": "A", "frame": 0, "mask": [[10, 20]]}]},  # run needs three numbers
        {"masks": [{"cell": "A", "frame": 0, "mask": []}]},  # entry for an invisible cell
        {"masks": [{"cell": "A", "frame": -1, "mask": [[1, 2, 3]]}]},
        {"masks": [{"cell": "A", "frame": 0, "mask": [[1, 2, 3]], "color": "#ff0000"}]},  # colors are not the agent's job
        {"masks": [], "revision": 1},
        {},
    ],
)
def test_the_cells_schema_rejects_what_the_model_rejects(broken):
    assert not jsonschema.Draft202012Validator(schema_for("cells")).is_valid(broken)
    with pytest.raises(ValueError):
        CellMasks.model_validate_json(json.dumps(broken))


def test_write_creates_the_file_and_parents(tmp_path):
    path = write("cells", tmp_path / "nested" / "schema.json")
    assert json.loads(path.read_text()) == schema_for("cells")
