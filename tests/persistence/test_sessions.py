from pathlib import Path

from wv.models import IngestSession, SessionImage
from wv.persistence.database import initialize_database
from wv.persistence.repositories import SessionImageRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope


def _create_session(repository: SessionRepository) -> IngestSession:
    return repository.create(
        IngestSession(
            id="20240628_120000__HNT001",
            device_id="HNT001",
            monitoring_site_id="SITE001",
            source_path="/Volumes/SD",
            mode="copy",
            recursive=False,
            started_at="2026-07-26T10:00:00+00:00",
            files_discovered=2,
        )
    )


def test_create_and_update_session(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        created = _create_session(SessionRepository(sql_session))

    with sql_session_scope(database_path) as sql_session:
        repository = SessionRepository(sql_session)
        updated = repository.update(
            created.id,
            {
                "completed_at": "2026-07-26T10:01:00+00:00",
                "ingest_status": "completed",
                "files_copied": 1,
                "files_ignored": 1,
            },
        )

    assert updated.ingest_status == "completed"
    assert updated.files_discovered == 2
    assert updated.files_copied == 1
    assert updated.files_ignored == 1


def test_create_or_replace_session_image_by_initial_path(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        repository = SessionImageRepository(sql_session)
        first = repository.create_or_replace_by_initial_path(
            SessionImage(
                id="image-1",
                session_id="20240628_120000__HNT001",
                source_relative_path="DCIM/first.jpg",
                initial_relative_path="init/capture.jpg",
                current_relative_path="init/capture.jpg",
                state="init",
                content_digest="AAAAAA111111",
                content_size_bytes=100,
                captured_at="2024-06-28T10:15:30",
                ingested_at="2026-07-26T10:00:00+00:00",
            )
        )
        replaced = repository.create_or_replace_by_initial_path(
            SessionImage(
                id="image-2",
                session_id="20240628_120000__HNT001",
                source_relative_path="DCIM/second.jpg",
                initial_relative_path="init/capture.jpg",
                current_relative_path="init/capture.jpg",
                state="init",
                content_digest="BBBBBB222222",
                content_size_bytes=120,
                captured_at="2024-06-28T10:15:30",
                ingested_at="2026-07-26T10:01:00+00:00",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        images = SessionImageRepository(sql_session).list_for_session(
            "20240628_120000__HNT001"
        )

    assert replaced.id == first.id
    assert images == [replaced]
    assert images[0].source_relative_path == "DCIM/second.jpg"
    assert images[0].content_digest == "BBBBBB222222"
