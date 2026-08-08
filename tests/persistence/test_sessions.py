from pathlib import Path

import pytest
from wv.domain.monitoring_area import MonitoringArea
from wv.domain.monitoring_site import MonitoringSite
from wv.domain.session import IngestSession, SessionImage, SessionProcessImagePlan
from wv.persistence.database import initialize_database
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import (
    SessionImageRepository,
    MonitoringAreaRepository,
    MonitoringSiteRepository,
    SessionProcessRepository,
    SessionProcessImagePlanRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope


def _create_session(repository: SessionRepository) -> IngestSession:
    MonitoringAreaRepository(repository.sql_session).create(
        MonitoringArea(id="AREA001", name="North Ranch")
    )
    MonitoringSiteRepository(repository.sql_session).create(
        MonitoringSite(
            id="SITE001",
            monitoring_area_id="AREA001",
            name="North Ridge",
            latitude=28.55,
            longitude=-101.14,
        )
    )
    return repository.create(
        IngestSession(
            id="20240628_120000__HNT001",
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


def test_create_session_rejects_missing_monitoring_site(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        with pytest.raises(PersistenceError, match="FOREIGN KEY constraint failed"):
            SessionRepository(sql_session).create(
                IngestSession(
                    id="20240628_120000__MISSING",
                    monitoring_site_id="MISSING",
                    source_path="/Volumes/SD",
                    mode="copy",
                    recursive=False,
                    started_at="2026-07-26T10:00:00+00:00",
                )
            )


def test_list_sessions_filters_limits_and_orders_newest_first(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    sessions = [
        IngestSession(
            id="20240628_120000__HNT001",
            monitoring_site_id="SITE001",
            source_path="/Volumes/SD1",
            mode="copy",
            recursive=False,
            started_at="2026-07-26T10:00:00+00:00",
            ingest_status="completed",
        ),
        IngestSession(
            id="20240629_120000__HNT001",
            monitoring_site_id="SITE001",
            source_path="/Volumes/SD1",
            mode="copy",
            recursive=False,
            started_at="2026-07-27T10:00:00+00:00",
            ingest_status="completed",
        ),
        IngestSession(
            id="20240630_120000__HNT002",
            monitoring_site_id="SITE002",
            source_path="/Volumes/SD2",
            mode="copy",
            recursive=False,
            started_at="2026-07-28T10:00:00+00:00",
            ingest_status="failed",
        ),
    ]
    with sql_session_scope(database_path) as sql_session:
        MonitoringAreaRepository(sql_session).create(
            MonitoringArea(id="AREA001", name="North Ranch")
        )
        site_repository = MonitoringSiteRepository(sql_session)
        site_repository.create(
            MonitoringSite("SITE001", "AREA001", "North Ridge", 28.55, -101.14)
        )
        site_repository.create(
            MonitoringSite("SITE002", "AREA001", "South Ridge", 28.56, -101.15)
        )
        repository = SessionRepository(sql_session)
        for session in sessions:
            repository.create(session)

    with sql_session_scope(database_path) as sql_session:
        result = SessionRepository(sql_session).list(
            monitoring_site_id="SITE001",
            ingest_status="completed",
            limit=1,
            newest_first=True,
        )

    assert [session.id for session in result] == ["20240629_120000__HNT001"]


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


def test_relocate_session_image(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        image = SessionImageRepository(sql_session).create_or_replace_by_initial_path(
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
        relocated = SessionImageRepository(sql_session).relocate(
            image.id,
            "ignored/corrupted/capture.jpg",
            "ignored/corrupted",
        )

    assert relocated.current_relative_path == "ignored/corrupted/capture.jpg"
    assert relocated.state == "ignored/corrupted"


def test_count_session_images_by_state(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        repository = SessionImageRepository(sql_session)
        for index, state in enumerate(["init", "detection/animal", "init"], start=1):
            repository.create_or_replace_by_initial_path(
                SessionImage(
                    id=f"image-{index}",
                    session_id="20240628_120000__HNT001",
                    source_relative_path=f"DCIM/{index}.jpg",
                    initial_relative_path=f"init/{index}.jpg",
                    current_relative_path=f"{state}/{index}.jpg",
                    state=state,
                    content_digest=f"DIGEST-{index}",
                    content_size_bytes=100,
                    captured_at="2024-06-28T10:15:30",
                    ingested_at="2026-07-26T10:00:00+00:00",
                )
            )

        counts = repository.count_by_state_for_session(
            "20240628_120000__HNT001"
        )

    assert [(item.state, item.count) for item in counts] == [
        ("detection/animal", 1),
        ("init", 2),
    ]


def test_start_and_complete_session_process(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        repository = SessionProcessRepository(sql_session)
        started = repository.start(
            "20240628_120000__HNT001",
            "clean_corrupted",
            "2026-07-26T10:01:00+00:00",
            parameters_json=None,
        )
        completed = repository.complete(
            started.session_id,
            started.process_name,
            status="completed",
            completed_at="2026-07-26T10:02:00+00:00",
            files_discovered=2,
            files_processed=2,
            files_selected=1,
            files_moved=1,
            files_ignored=0,
            files_failed=0,
        )

    assert completed.status == "completed"
    assert completed.attempt_count == 1
    assert completed.files_moved == 1


def test_list_session_processes_for_session(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        repository = SessionProcessRepository(sql_session)
        repository.start(
            "20240628_120000__HNT001",
            "clean_corrupted",
            "2026-07-26T10:01:00+00:00",
            parameters_json=None,
        )
        repository.start(
            "20240628_120000__HNT001",
            "clean_bursts",
            "2026-07-26T10:02:00+00:00",
            parameters_json="{}",
        )

        processes = repository.list_for_session("20240628_120000__HNT001")

    assert [process.process_name for process in processes] == [
        "clean_bursts",
        "clean_corrupted",
    ]


def test_create_and_list_session_process_image_plans(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        _create_session(SessionRepository(sql_session))
        SessionImageRepository(sql_session).create_or_replace_by_initial_path(
            SessionImage(
                id="image-1",
                session_id="20240628_120000__HNT001",
                source_relative_path="DCIM/capture.jpg",
                initial_relative_path="init/capture.jpg",
                current_relative_path="init/capture.jpg",
                state="init",
                content_digest="AAAAAA111111",
                content_size_bytes=100,
                captured_at="2024-06-28T10:15:30",
                ingested_at="2026-07-26T10:00:00+00:00",
            )
        )
        SessionProcessRepository(sql_session).start(
            "20240628_120000__HNT001",
            "clean_bursts",
            "2026-07-26T10:01:00+00:00",
            parameters_json="{}",
        )
        created = SessionProcessImagePlanRepository(sql_session).create_many(
            [
                SessionProcessImagePlan(
                    session_id="20240628_120000__HNT001",
                    process_name="clean_bursts",
                    image_id="image-1",
                    decision="move",
                    target_relative_path="ignored/bursts/capture.jpg",
                    planned_at="2026-07-26T10:01:00+00:00",
                )
            ]
        )

    with sql_session_scope(database_path) as sql_session:
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            "20240628_120000__HNT001", "clean_bursts"
        )

    assert plans == created
