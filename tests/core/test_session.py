from pathlib import Path

import pytest

from wv.core.session import (
    DETECTION_LABELS,
    get_detection_path,
    get_ignored_bursts_path,
    get_ignored_corrupted_path,
    get_ignored_overexposed_path,
    get_init_path,
    require_session_component,
)


def test_session_routes_are_canonical(tmp_path: Path):
    session_path = tmp_path / "20260707_101530__HNT001"

    assert get_init_path(session_path) == session_path / "init"
    assert get_ignored_corrupted_path(session_path) == session_path / "ignored" / "corrupted"
    assert get_ignored_overexposed_path(session_path) == session_path / "ignored" / "overexposed"
    assert get_ignored_bursts_path(session_path) == session_path / "ignored" / "bursts"
    assert DETECTION_LABELS == ("animal", "vehicle", "human", "domestic", "other", "empty")
    assert get_detection_path(session_path) == session_path / "detection"
    assert get_detection_path(session_path, "animal") == session_path / "detection" / "animal"


@pytest.mark.parametrize("value", ["../escape", "camera-01"])
def test_require_session_component_rejects_unsafe_values(value: str):
    with pytest.raises(ValueError, match="letters, digits, and underscores"):
        require_session_component(value, "Device ID")
