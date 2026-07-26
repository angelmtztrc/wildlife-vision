from datetime import datetime
from pathlib import Path

import pytest

import wv.use_cases.ingest.ingest as ingest
import wv.use_cases.ingest._shared as ingest_shared
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.ingest._shared import IngestError
from wv.use_cases.sd.initialize import SdInitializeInput, run as run_initialize_sd
from wv.workspace.workspace_config import get_workspace_database_path


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def _freeze_ingest_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_shared, "datetime", FrozenDateTime)
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
            mode="copy",
            identity=ingest.ExplicitIngestIdentity(
                device_id="HNT001",
                monitoring_site_id="SITE001",
            ),
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
            mode="drain",
            identity=ingest.ExplicitIngestIdentity(
                device_id="HNT001",
                monitoring_site_id="SITE001",
            ),
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

    with pytest.raises(IngestError, match="Monitoring site not found: UNKNOWN"):
        ingest.run(
            ingest.IngestInput(
                source=source,
                mode="copy",
                identity=ingest.ExplicitIngestIdentity(
                    device_id="HNT001",
                    monitoring_site_id="UNKNOWN",
                ),
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
            mode="copy",
            identity=ingest.ExplicitIngestIdentity(
                device_id="HNT001",
                monitoring_site_id="SITE001",
            ),
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
    monkeypatch.setattr(ingest_shared, "datetime", FrozenDateTime)

    result = ingest.run(
        ingest.IngestInput(
            source=source,
            mode="copy",
            identity=ingest.ExplicitIngestIdentity(
                device_id="HNT001",
                monitoring_site_id="SITE001",
            ),
        )
    )

    assert result.files_copied == 0
    assert result.files_ignored == 1
    assert result.destination.is_dir()


def test_run_sd_rejects_database_assignment_mismatch(
    configured_workspace: Path,
    tmp_path: Path,
):
    source = tmp_path / "sd-card"
    source.mkdir()
    run_initialize_sd(
        SdInitializeInput(path=source, device_id="HNT001", monitoring_site_id="SITE001")
    )

    with sql_session_scope(get_workspace_database_path(configured_workspace)) as sql_session:
        DeviceRepository(sql_session).update(
            "HNT001", {"monitoring_site_id": "SITE002"}
        )

    with pytest.raises(IngestError, match="wv sd sync"):
        ingest.run(
            ingest.IngestInput(
                source=source,
                mode="copy",
                identity=ingest.SdCardIngestIdentity(),
            )
        )
