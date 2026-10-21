import json

import jsonschema
import pytest

from cell_tracking.masks import EXAMPLE, CellMasks
from cell_tracking.schema import render, schema, write


def test_the_schema_is_derived_from_the_model_and_carries_its_guidance():
    derived = schema()
    assert "no entry for that frame" in derived["description"]
    assert derived["examples"] == [EXAMPLE]
    assert derived["$defs"]["CellMask"]["properties"]["mask"]["minItems"] == 1
    assert "exclusive x_end" in derived["$defs"]["CellMask"]["properties"]["mask"]["description"]
    assert render() == json.dumps(derived, indent=2) + "\n"


def test_the_example_is_valid_under_the_schema_and_the_model():
    CellMasks.model_validate_json(json.dumps(EXAMPLE))
    jsonschema.Draft202012Validator(schema()).validate(EXAMPLE)


def test_the_schema_does_not_use_the_word_neuron():
    assert "neuron" not in render().lower()


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
def test_the_schema_rejects_what_the_model_rejects(broken):
    assert not jsonschema.Draft202012Validator(schema()).is_valid(broken)
    with pytest.raises(ValueError):
        CellMasks.model_validate_json(json.dumps(broken))


def test_write_creates_the_file_and_parents(tmp_path):
    path = write(tmp_path / "nested" / "schema.json")
    assert json.loads(path.read_text()) == schema()
