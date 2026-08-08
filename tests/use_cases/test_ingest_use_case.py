from datetime import datetime
from pathlib import Path

import pytest

import wv.use_cases.ingest._shared as ingest_shared
import wv.use_cases.ingest.ingest as ingest
from wv.core.files import get_content_digest
from wv.persistence.repositories import SessionImageRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.ingest._shared import IngestError
from wv.workspace.workspace_config import get_workspace_database_path


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def _input(source: Path, *, mode: str = "copy", recursive: bool = False, dry_run: bool = False):
    return ingest.IngestInput(
        source=source,
        mode=mode,
        identity=ingest.ExplicitIngestIdentity(monitoring_site_id="SITE001"),
        recursive=recursive,
        dry_run=dry_run,
    )


def _freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_shared, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        ingest, "get_image_datetime", lambda path: datetime(2024, 6, 28, 10, 15, 30)
    )


def test_recursive_ingest_records_site_based_session_and_inventory(
    configured_workspace: Path, make_image, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    image = make_image(source / "DCIM" / "capture.jpg")
    _freeze(monkeypatch)

    result = ingest.run(_input(source, recursive=True))
    session_id = "20240628_120000__SITE001"
    with sql_session_scope(get_workspace_database_path(configured_workspace)) as sql_session:
        session = SessionRepository(sql_session).get(session_id)
        images = SessionImageRepository(sql_session).list_for_session(session_id)

    assert result.destination == configured_workspace / "sessions" / session_id / "init"
    assert session.monitoring_site_id == "SITE001"
    assert session.ingest_status == "completed"
    assert images[0].content_digest == get_content_digest(image)


def test_recursive_ingest_skips_wv_metadata_and_unsupported_files(
    configured_workspace: Path, make_image, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    make_image(source / "capture.jpg")
    make_image(source / "nested" / "nested.jpg")
    make_image(source / ".wv" / "ignored.jpg")
    (source / "notes.txt").write_text("ignore")
    _freeze(monkeypatch)

    result = ingest.run(_input(source, recursive=True, dry_run=True))

    assert result.files_discovered == 3
    assert result.files_copied == 2
    assert result.files_ignored == 1


def test_drain_deletes_source_after_verified_copy(
    configured_workspace: Path, make_image, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    image = make_image(source / "capture.jpg")
    _freeze(monkeypatch)

    result = ingest.run(_input(source, mode="drain"))

    assert result.files_copied == 1
    assert result.files_deleted == 1
    assert not image.exists()


def test_ingest_rejects_unknown_monitoring_site(configured_workspace: Path, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    request = ingest.IngestInput(
        source=source,
        mode="copy",
        identity=ingest.ExplicitIngestIdentity(monitoring_site_id="UNKNOWN"),
    )

    with pytest.raises(IngestError, match="Monitoring site not found: UNKNOWN"):
        ingest.run(request)
