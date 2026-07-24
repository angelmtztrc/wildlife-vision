from datetime import datetime
from pathlib import Path

import pytest

import wv.use_cases.ingest as ingest
from wv.persistence.common import RecordNotFoundError


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def _freeze_ingest_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        ingest,
        "get_image_datetime",
        lambda file_path: datetime(2024, 6, 28, 10, 15, 30),
    )


def test_run_dry_copy_uses_identity_and_workspace_session(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    (source / "notes.txt").write_text("ignore me")
    (source / "subdir").mkdir()
    _freeze_ingest_environment(monkeypatch)

    result = ingest.run(
        ingest.IngestInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="copy",
            dry_run=True,
        )
    )

    assert result.destination == (
        configured_workspace / "sessions" / "20240628_120000__HNT001" / "init"
    )
    assert result.files_discovered == 3
    assert result.files_copied == 1
    assert result.files_deleted == 0
    assert result.files_ignored == 2
    assert result.files_failed == 0
    assert result.dry_run is True
    assert image_path.exists()
    assert not result.destination.exists()


def test_run_drain_writes_expected_file_and_deletes_source(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    _freeze_ingest_environment(monkeypatch)

    file_id = ingest.get_file_id(image_path)
    result = ingest.run(
        ingest.IngestInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="drain",
        )
    )
    expected_destination = (
        configured_workspace
        / "sessions"
        / "20240628_120000__HNT001"
        / "init"
        / f"20240628_101530__SITE001__{file_id}.jpg"
    )

    assert result.files_copied == 1
    assert result.files_deleted == 1
    assert result.files_failed == 0
    assert expected_destination.exists()
    assert not image_path.exists()


def test_run_rejects_unregistered_identity(configured_workspace: Path, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(RecordNotFoundError, match="Monitoring site not found: UNKNOWN"):
        ingest.run(
            ingest.IngestInput(
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
    _freeze_ingest_environment(monkeypatch)
    (configured_workspace / "sessions" / "20240628_120000__HNT001").mkdir()

    result = ingest.run(
        ingest.IngestInput(
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
    monkeypatch.setattr(ingest, "datetime", FrozenDateTime)

    result = ingest.run(
        ingest.IngestInput(
            source=source,
            device_id="HNT001",
            monitoring_site_id="SITE001",
            mode="copy",
        )
    )

    assert result.files_copied == 0
    assert result.files_ignored == 1
    assert result.destination.is_dir()
