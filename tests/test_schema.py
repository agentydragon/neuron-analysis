import json

import jsonschema

from neuron_tracking.annotations import Annotations
from neuron_tracking.schema import EXAMPLE, IDENTITY, SHARED, identity_schema, render, shared_schema


def test_published_schemas_are_generated_from_the_model():
    assert SHARED.read_text() == render(shared_schema())
    assert IDENTITY.read_text() == render(identity_schema())


def test_example_is_a_valid_annotation_under_both_schemas():
    Annotations.model_validate_json(json.dumps(EXAMPLE))
    for schema in (shared_schema(), identity_schema()):
        jsonschema.Draft202012Validator(schema).validate(EXAMPLE)


def test_neither_schema_uses_the_word_neuron():
    assert "neuron" not in (render(shared_schema()) + render(identity_schema())).lower()


def test_schema_rejects_what_the_model_rejects_at_the_structure_level():
    broken = json.loads(json.dumps(EXAMPLE))
    broken["observations"][0]["body"] = [[10, 20]]
    for schema in (shared_schema(), identity_schema()):
        assert not jsonschema.Draft202012Validator(schema).is_valid(broken)
