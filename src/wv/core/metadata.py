"""Helpers for wildlife-vision metadata stored in EXIF descriptions."""


def parse_image_description(value: str | None) -> dict[str, str]:
    """Parse ``key=value;`` metadata from EXIF ``ImageDescription`` text.

    Args:
        value: Description text to parse, or ``None`` when no metadata exists.

    Returns:
        Parsed properties in encounter order. Empty keys and fragments without
        an equals sign are ignored; repeated keys keep their final value.

    Notes:
        The format has no escaping mechanism, so semicolons and equals signs in
        values cannot round-trip without ambiguity.
    """
    if not value:
        return {}

    properties: dict[str, str] = {}

    for fragment in value.split(";"):
        if "=" not in fragment:
            continue

        key, property_value = fragment.split("=", 1)
        key = key.strip()

        if not key:
            continue

        properties[key] = property_value.strip()

    return properties


def serialize_image_description(properties: dict[str, str]) -> str:
    """Serialize metadata to canonical ``key=value;`` EXIF text.

    Args:
        properties: Metadata properties to serialize in insertion order.

    Returns:
        An empty string for no properties; otherwise, semicolon-terminated
        key-value pairs. Entries with empty keys are omitted.
    """
    if not properties:
        return ""

    return "".join(f"{key}={value};" for key, value in properties.items() if key)


def upsert_image_description_properties(
    existing: str | None, updates: dict[str, str]
) -> str:
    """Parse existing metadata, apply updates, and serialize the result.

    Args:
        existing: Existing EXIF description text, if present.
        updates: Properties to insert or overwrite.

    Returns:
        Canonical serialized metadata preserving existing property order while
        replacing values for matching update keys.
    """
    properties = parse_image_description(existing)

    for key, value in updates.items():
        properties[key] = value

    return serialize_image_description(properties)
