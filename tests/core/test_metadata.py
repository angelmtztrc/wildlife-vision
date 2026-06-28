from wv.core.metadata import (
    parse_image_description,
    serialize_image_description,
    upsert_image_description_properties,
)


def test_parse_image_description_ignores_malformed_fragments():
    assert parse_image_description("Camera=HNT001;broken;=value;Detection=animal;") == {
        "Camera": "HNT001",
        "Detection": "animal",
    }


def test_serialize_image_description_uses_canonical_format():
    assert serialize_image_description({"Camera": "HNT001", "Detection": "animal"}) == (
        "Camera=HNT001;Detection=animal;"
    )


def test_upsert_image_description_properties_preserves_valid_entries_and_rewrites():
    value = upsert_image_description_properties(
        "Camera=HNT001;broken;Detection=animal;",
        {"Detection": "human", "Detection_Confidence": "0.92"},
    )

    assert value == "Camera=HNT001;Detection=human;Detection_Confidence=0.92;"
