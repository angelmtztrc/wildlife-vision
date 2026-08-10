from pathlib import Path

import pytest

from wv.domain.session import IngestSession
from wv.persistence.repositories import SessionProcessRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.list import ListSessionsInput, run
from wv.workspace.workspace_config import require_workspace_database_path


def _create_session(
    workspace_path: Path,
    *,
    session_id: str,
    monitoring_site_id: str,
    started_at: str,
    ingest_status: str,
) -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=session_id,
                monitoring_site_id=monitoring_site_id,
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at=started_at,
                ingest_status=ingest_status,
            )
        )


def _complete_processing(
    workspace_path: Path, session_id: str, *, with_failures: bool = False
) -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        for index, process_name in enumerate(
            ("clean_corrupted", "clean_overexposed_ir", "detect_content"), start=1
        ):
            repository.start(
                session_id,
                process_name,
                f"2026-08-01T12:0{index}:00+00:00",
                parameters_json="{}",
            )
            repository.complete(
                session_id,
                process_name,
                status=(
                    "completed_with_failures"
                    if with_failures and process_name == "detect_content"
                    else "completed"
                ),
                completed_at=f"2026-08-01T12:0{index}:30+00:00",
                files_discovered=0,
                files_processed=0,
                files_selected=0,
                files_moved=0,
                files_ignored=0,
                files_failed=1 if with_failures and process_name == "detect_content" else 0,
            )


def test_run_lists_newest_sessions_with_combined_filters(configured_workspace: Path):
    _create_session(
        configured_workspace,
        session_id="20260801_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-01T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260802_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-02T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260803_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-03T12:00:00+00:00",
        ingest_status="failed",
    )

    result = run(
        ListSessionsInput(
            monitoring_site_id="SITE001",
            ingest_status="completed",
            limit=1,
        )
    )

    assert [session.id for session in result.items] == [
        "20260802_120000__SITE001"
    ]
    assert result.items[0].processing_status == "ready"
    assert result.items[0].next_action == "run"
    assert result.items[0].next_process == "clean_corrupted"


def test_run_derives_processing_status_from_bulk_process_records(
    configured_workspace: Path,
):
    session_id = "20260801_120000__SITE001"
    _create_session(
        configured_workspace,
        session_id=session_id,
        monitoring_site_id="SITE001",
        started_at="2026-08-01T12:00:00+00:00",
        ingest_status="completed",
    )
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            session_id,
            "clean_corrupted",
            "2026-08-01T12:01:00+00:00",
            parameters_json=None,
        )
        repository.complete(
            session_id,
            "clean_corrupted",
            status="completed",
            completed_at="2026-08-01T12:02:00+00:00",
            files_discovered=0,
            files_processed=0,
            files_selected=0,
            files_moved=0,
            files_ignored=0,
            files_failed=0,
        )

    result = run(ListSessionsInput())

    assert result.items[0].processing_status == "processing"
    assert result.items[0].next_action == "run"
    assert result.items[0].next_process == "clean_overexposed_ir"


def test_run_lists_incomplete_sessions_before_newer_completed_sessions(
    configured_workspace: Path,
):
    _create_session(
        configured_workspace,
        session_id="20260801_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-01T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260802_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-02T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260803_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-03T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260804_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-04T12:00:00+00:00",
        ingest_status="completed",
    )
    _complete_processing(configured_workspace, "20260802_120000__SITE001")
    _complete_processing(configured_workspace, "20260803_120000__SITE001", with_failures=True)
    _complete_processing(configured_workspace, "20260804_120000__SITE001")

    result = run(ListSessionsInput(limit=3))

    assert [item.id for item in result.items] == [
        "20260803_120000__SITE001",
        "20260801_120000__SITE001",
        "20260804_120000__SITE001",
    ]
    assert [item.processing_status for item in result.items] == [
        "completed_with_failures",
        "ready",
        "completed",
    ]


@pytest.mark.parametrize(
    ("input_data", "message"),
    [
        (ListSessionsInput(limit=0), "limit"),
        (ListSessionsInput(ingest_status="unknown"), "Unknown ingest status"),
    ],
)
def test_run_rejects_invalid_filters(
    configured_workspace: Path,
    input_data: ListSessionsInput,
    message: str,
):
    with pytest.raises(SessionError, match=message):
        run(input_data)
