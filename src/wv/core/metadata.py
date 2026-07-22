def parse_image_description(value: str | None) -> dict[str, str]:
    """Parse wildlife-vision metadata from EXIF ``ImageDescription`` text."""
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
    """Serialize wildlife-vision metadata to canonical EXIF text."""
    if not properties:
        return ""

    return "".join(f"{key}={value};" for key, value in properties.items() if key)


def upsert_image_description_properties(
    existing: str | None, updates: dict[str, str]
) -> str:
    """Best-effort parse ``existing`` metadata and upsert ``updates``."""
    properties = parse_image_description(existing)

    for key, value in updates.items():
        properties[key] = value

    return serialize_image_description(properties)
