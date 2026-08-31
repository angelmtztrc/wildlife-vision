"""Stable identifier normalization for user-managed catalogs."""

import re
import unicodedata

_SEPARATOR_PATTERN = re.compile(r"[^A-Z0-9]+")


def normalize_catalog_identifier(value: str) -> str:
    """Create a filesystem-safe catalog identifier from a name or override.

    Accented characters are transliterated to ASCII, letters are uppercased, and
    consecutive punctuation or whitespace becomes one underscore. The result is
    suitable for monitoring-area and monitoring-site IDs, which are later used
    in session paths and image filenames.

    Args:
        value: Human-readable name or explicit identifier to normalize.

    Returns:
        An uppercase identifier containing only letters, digits, and underscores.

    Raises:
        ValueError: If ``value`` contains no ASCII letters or digits after
            normalization.
    """
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode(
        "ascii"
    )
    identifier = _SEPARATOR_PATTERN.sub("_", normalized.upper()).strip("_")
    if not identifier:
        raise ValueError("Identifier must contain at least one letter or digit.")
    return identifier
