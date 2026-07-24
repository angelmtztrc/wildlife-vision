"""Canonical session-directory names and pure path construction helpers."""

import re
from pathlib import Path

INIT_DIRECTORY = "init"
IGNORED_DIRECTORY = "ignored"
DETECTION_DIRECTORY = "detection"
DETECTION_LABELS = ("animal", "vehicle", "human", "other", "empty")
_SESSION_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def require_session_component(value: str, field: str) -> str:
    """Validate a value used as a session path component.

    Args:
        value: Device, monitoring-site, or other component value to validate.
        field: Human-readable field name used in the validation error.

    Returns:
        The unchanged validated value.

    Raises:
        ValueError: If ``value`` contains characters other than letters, digits,
            or underscores.
    """
    if not _SESSION_COMPONENT_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must contain only letters, digits, and underscores.")
    return value


def get_init_path(session_path: Path) -> Path:
    """Return the initial-ingest route for a session without creating it.

    Args:
        session_path: Root directory of an ingest session.

    Returns:
        The ``init`` directory path beneath ``session_path``.
    """
    return session_path / INIT_DIRECTORY


def get_ignored_corrupted_path(session_path: Path) -> Path:
    """Return the corrupted-image ignore route without creating it.

    Args:
        session_path: Root directory of an ingest session.

    Returns:
        The ``ignored/corrupted`` directory path beneath ``session_path``.
    """
    return session_path / IGNORED_DIRECTORY / "corrupted"


def get_ignored_overexposed_path(session_path: Path) -> Path:
    """Return the overexposed-image ignore route without creating it.

    Args:
        session_path: Root directory of an ingest session.

    Returns:
        The ``ignored/overexposed`` directory path beneath ``session_path``.
    """
    return session_path / IGNORED_DIRECTORY / "overexposed"


def get_ignored_bursts_path(session_path: Path) -> Path:
    """Return the burst-image ignore route without creating it.

    Args:
        session_path: Root directory of an ingest session.

    Returns:
        The ``ignored/bursts`` directory path beneath ``session_path``.
    """
    return session_path / IGNORED_DIRECTORY / "bursts"


def get_detection_path(session_path: Path, label: str | None = None) -> Path:
    """Return a detection route for a session without creating it.

    Args:
        session_path: Root directory of an ingest session.
        label: Optional supported detection label. Omit it for the shared
            ``detection`` root.

    Returns:
        The detection root or the directory for ``label`` beneath it.

    Raises:
        ValueError: If ``label`` is not in ``DETECTION_LABELS``.
    """
    path = session_path / DETECTION_DIRECTORY
    if label is None:
        return path
    if label not in DETECTION_LABELS:
        raise ValueError(f"Unknown detection label: {label}")
    return path / label
