from datetime import datetime
from pathlib import Path

import pytest

import wv.use_cases.ingest.common as common
from wv.persistence.common import RecordNotFoundError
from wv.use_cases.ingest.folder import IngestFolderInput, run


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def test_run_copy_uses_option_identity_and_workspace_session(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    monkeypatch.setattr(common, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        common,
        "get_image_datetime",
        lambda file_path: datetime(2024, 6, 28, 10, 15, 30),
    )

    result = run(
        IngestFolderInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="copy",
        )
    )

    file_id = common.get_file_id(image_path)
    expected_destination = (
        configured_workspace
        / "sessions"
        / "20240628_120000__HNT001"
        / "init"
        / f"20240628_101530__SITE001__{file_id}.jpg"
    )
    assert result.destination == expected_destination.parent
    assert expected_destination.exists()
    assert image_path.exists()


def test_run_rejects_unregistered_option_identity(
    configured_workspace: Path, tmp_path: Path
):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(RecordNotFoundError, match="Monitoring site not found: UNKNOWN"):
        run(
            IngestFolderInput(
                source=source,
                device_id="HNT001",
                monitoring_site_id="UNKNOWN",
                mode="copy",
            )
        )


def test_run_uses_next_timestamp_when_session_already_exists(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    make_image(source / "capture.jpg")
    monkeypatch.setattr(common, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        common,
        "get_image_datetime",
        lambda file_path: datetime(2024, 6, 28, 10, 15, 30),
    )
    (configured_workspace / "sessions" / "20240628_120000__HNT001").mkdir()

    result = run(
        IngestFolderInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="copy",
        )
    )

    assert result.destination == (
        configured_workspace / "sessions" / "20240628_120001__HNT001" / "init"
    )


def test_run_creates_init_route_for_unsupported_only_source(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("ignore me")
    monkeypatch.setattr(common, "datetime", FrozenDateTime)

    result = run(
        IngestFolderInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="copy",
        )
    )

    assert result.files_copied == 0
    assert result.files_ignored == 1
    assert result.destination.is_dir()
