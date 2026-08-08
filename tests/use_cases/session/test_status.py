from pathlib import Path

import pytest

from wv.domain.session import IngestSession, SessionImage
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.status import SessionStatusInput, run
from wv.workspace.workspace_config import require_workspace_database_path


SESSION_ID = "20260801_120000__HNT001"


def _create_session(
    workspace_path: Path,
    *,
    ingest_status: str = "completed",
    create_paths: bool = True,
) -> None:
    if create_paths:
        (workspace_path / "sessions" / SESSION_ID / "init").mkdir(parents=True)

    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=SESSION_ID,
                monitoring_site_id="SITE001",
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at="2026-08-01T12:00:00+00:00",
                completed_at="2026-08-01T12:01:00+00:00",
                ingest_status=ingest_status,
                files_discovered=2,
                files_copied=2,
            )
        )


def _complete_processes(
    workspace_path: Path, statuses: list[str]
) -> None:
    process_names = [
        "clean_corrupted",
        "clean_overexposed_ir",
        "clean_bursts",
        "detect_content",
    ]
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        for index, (process_name, status) in enumerate(
            zip(process_names, statuses, strict=True), start=1
        ):
            repository.start(
                SESSION_ID,
                process_name,
                f"2026-08-01T12:0{index}:00+00:00",
                parameters_json=f'{{"stage":{index}}}',
            )
            repository.complete(
                SESSION_ID,
                process_name,
                status=status,
                completed_at=f"2026-08-01T12:1{index}:00+00:00",
                files_discovered=2,
                files_processed=2,
                files_selected=0,
                files_moved=0,
                files_ignored=0,
                files_failed=1 if status == "completed_with_failures" else 0,
            )


def test_run_reports_ready_session_inventory_and_filesystem(configured_workspace: Path):
    _create_session(configured_workspace)
    with sql_session_scope(
        require_workspace_database_path(configured_workspace)
    ) as sql_session:
        repository = SessionImageRepository(sql_session)
        for index, state in enumerate(["init", "detection/animal"], start=1):
            repository.create_or_replace_by_initial_path(
                SessionImage(
                    id=f"image-{index}",
                    session_id=SESSION_ID,
                    source_relative_path=f"DCIM/{index}.jpg",
                    initial_relative_path=f"init/{index}.jpg",
                    current_relative_path=f"{state}/{index}.jpg",
                    state=state,
                    content_digest=f"DIGEST-{index}",
                    content_size_bytes=100,
                    captured_at="2026-08-01T11:00:00",
                    ingested_at="2026-08-01T12:00:00+00:00",
                )
            )

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "ready"
    assert result.next_process == "clean_corrupted"
    assert result.next_action == "run"
    assert [stage.status for stage in result.stages] == ["not_started"] * 4
    assert [(item.state, item.count) for item in result.inventory] == [
        ("detection/animal", 1),
        ("init", 1),
    ]
    assert result.filesystem is not None
    assert result.filesystem.status == "available"


def test_run_reports_retry_for_latest_stage_with_failures(configured_workspace: Path):
    _create_session(configured_workspace)
    with sql_session_scope(
        require_workspace_database_path(configured_workspace)
    ) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_corrupted",
            "2026-08-01T12:02:00+00:00",
            parameters_json=None,
        )
        repository.complete(
            SESSION_ID,
            "clean_corrupted",
            status="completed_with_failures",
            completed_at="2026-08-01T12:03:00+00:00",
            files_discovered=2,
            files_processed=2,
            files_selected=1,
            files_moved=1,
            files_ignored=0,
            files_failed=1,
        )

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "processing_with_failures"
    assert result.next_process == "clean_corrupted"
    assert result.next_action == "retry"
    assert result.stages[0].files_failed == 1


def test_run_keeps_missing_filesystem_diagnostic_non_fatal(configured_workspace: Path):
    _create_session(configured_workspace, ingest_status="failed", create_paths=False)

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "ingest_failed"
    assert result.filesystem is not None
    assert result.filesystem.status == "missing"


def test_run_blocks_next_action_when_completed_ingest_filesystem_is_missing(
    configured_workspace: Path,
):
    _create_session(configured_workspace, create_paths=False)

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "filesystem_blocked"
    assert result.next_process is None
    assert result.next_action is None
    assert result.filesystem is not None
    assert result.filesystem.status == "missing"


def test_run_reports_retry_for_final_stage_with_failures(configured_workspace: Path):
    _create_session(configured_workspace)
    _complete_processes(
        configured_workspace,
        ["completed", "completed", "completed", "completed_with_failures"],
    )

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "completed_with_failures"
    assert result.next_process == "detect_content"
    assert result.next_action == "retry"
    assert result.stages[-1].parameters_json == '{"stage":4}'


def test_run_reports_inconsistent_successor_after_in_progress_stage(
    configured_workspace: Path,
):
    _create_session(configured_workspace)
    with sql_session_scope(
        require_workspace_database_path(configured_workspace)
    ) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_corrupted",
            "2026-08-01T12:02:00+00:00",
            parameters_json=None,
        )
        repository.start(
            SESSION_ID,
            "clean_overexposed_ir",
            "2026-08-01T12:03:00+00:00",
            parameters_json=None,
        )
        repository.complete(
            SESSION_ID,
            "clean_overexposed_ir",
            status="completed",
            completed_at="2026-08-01T12:04:00+00:00",
            files_discovered=0,
            files_processed=0,
            files_selected=0,
            files_moved=0,
            files_ignored=0,
            files_failed=0,
        )

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "inconsistent"
    assert result.next_process is None
    assert result.next_action is None


@pytest.mark.parametrize("status", ["in_progress", "failed"])
def test_run_reports_inconsistent_stage_after_missing_predecessor(
    configured_workspace: Path, status: str
):
    _create_session(configured_workspace)
    with sql_session_scope(
        require_workspace_database_path(configured_workspace)
    ) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_overexposed_ir",
            "2026-08-01T12:03:00+00:00",
            parameters_json=None,
        )
        if status == "failed":
            repository.fail(
                SESSION_ID,
                "clean_overexposed_ir",
                completed_at="2026-08-01T12:04:00+00:00",
                failure_message="failed",
            )

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "inconsistent"
    assert result.next_process is None
    assert result.next_action is None


def test_run_rejects_symlinked_sessions_directory_as_unsafe(
    configured_workspace: Path, tmp_path: Path
):
    _create_session(configured_workspace, create_paths=False)
    sessions_path = configured_workspace / "sessions"
    sessions_path.rmdir()
    external_sessions = tmp_path / "external-sessions"
    (external_sessions / SESSION_ID / "init").mkdir(parents=True)
    sessions_path.symlink_to(external_sessions, target_is_directory=True)

    result = run(SessionStatusInput(session_id=SESSION_ID))

    assert result.overall_status == "filesystem_blocked"
    assert result.filesystem is not None
    assert result.filesystem.status == "unsafe"


def test_run_rejects_unknown_session(configured_workspace: Path):
    with pytest.raises(SessionError, match="Session not found: MISSING"):
        run(SessionStatusInput(session_id="MISSING"))
