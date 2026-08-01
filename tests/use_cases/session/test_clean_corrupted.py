from dataclasses import replace
from pathlib import Path

import pytest

import wv.use_cases.session.clean_corrupted as managed_corrupted
from wv.models import IngestSession, SessionImage
from wv.core.files import get_content_digest
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session.clean_corrupted import (
    SessionCleanCorruptedInput,
    run,
)
from wv.use_cases.session._shared import SessionProcessError
from wv.workspace.workspace_config import require_workspace_database_path


SESSION_ID = "20240731_120000__HNT001"


def _create_session_inventory(
    workspace_path: Path,
    *,
    ingest_status: str = "completed",
    filename: str = "capture.jpg",
) -> tuple[Path, Path]:
    database_path = require_workspace_database_path(workspace_path)
    session_path = workspace_path / "sessions" / SESSION_ID
    init_path = session_path / "init"
    init_path.mkdir(parents=True)

    with sql_session_scope(database_path) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=SESSION_ID,
                device_id="HNT001",
                monitoring_site_id="SITE001",
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at="2026-07-31T12:00:00+00:00",
                ingest_status=ingest_status,
            )
        )
        SessionImageRepository(sql_session).create_or_replace_by_initial_path(
            SessionImage(
                id="image-1",
                session_id=SESSION_ID,
                source_relative_path=f"DCIM/{filename}",
                initial_relative_path=f"init/{filename}",
                current_relative_path=f"init/{filename}",
                state="init",
                content_digest="AAAAAA111111",
                content_size_bytes=100,
                captured_at="2024-07-31T12:00:00",
                ingested_at="2026-07-31T12:00:00+00:00",
            )
        )

    return session_path, init_path / filename


def _record_actual_image_content(workspace_path: Path, image_path: Path) -> None:
    database_path = require_workspace_database_path(workspace_path)
    with sql_session_scope(database_path) as sql_session:
        repository = SessionImageRepository(sql_session)
        image = repository.get("image-1")
        repository.create_or_replace_by_initial_path(
            replace(
                image,
                content_digest=get_content_digest(image_path),
                content_size_bytes=image_path.stat().st_size,
            )
        )


def test_run_moves_corrupted_image_and_updates_inventory(
    configured_workspace: Path, make_corrupted_image
):
    session_path, source_path = _create_session_inventory(configured_workspace)
    make_corrupted_image(source_path)
    _record_actual_image_content(configured_workspace, source_path)

    result = run(SessionCleanCorruptedInput(session_id=SESSION_ID))

    destination_path = session_path / "ignored" / "corrupted" / source_path.name
    assert result.process is not None
    assert result.process.status == "completed"
    assert result.process.files_moved == 1
    assert result.files_discovered == 1
    assert result.files_corrupted == 1
    assert result.files_moved == 1
    assert result.destination == session_path / "ignored" / "corrupted"
    assert result.dry_run is False
    assert not source_path.exists()
    assert destination_path.is_file()

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        image = SessionImageRepository(sql_session).get("image-1")

    assert image.current_relative_path == "ignored/corrupted/capture.jpg"
    assert image.state == "ignored/corrupted"


def test_run_rejects_completed_process(
    configured_workspace: Path, make_image
):
    _, source_path = _create_session_inventory(configured_workspace)
    make_image(source_path)
    _record_actual_image_content(configured_workspace, source_path)
    run(SessionCleanCorruptedInput(session_id=SESSION_ID))

    with pytest.raises(SessionProcessError, match="already completed"):
        run(SessionCleanCorruptedInput(session_id=SESSION_ID))


def test_run_reconciles_interrupted_move_with_recovery(
    configured_workspace: Path, make_corrupted_image
):
    session_path, source_path = _create_session_inventory(configured_workspace)
    make_corrupted_image(source_path)
    _record_actual_image_content(configured_workspace, source_path)
    destination_path = session_path / "ignored" / "corrupted" / source_path.name
    destination_path.parent.mkdir(parents=True)
    source_path.replace(destination_path)

    database_path = require_workspace_database_path(configured_workspace)
    with sql_session_scope(database_path) as sql_session:
        SessionProcessRepository(sql_session).start(
            SESSION_ID,
            "clean_corrupted",
            "2026-07-31T12:01:00+00:00",
            parameters_json=None,
        )

    result = run(SessionCleanCorruptedInput(session_id=SESSION_ID, recover=True))

    assert result.process is not None
    assert result.process.status == "completed"
    assert result.process.attempt_count == 2
    assert result.process.files_moved == 1
    with sql_session_scope(database_path) as sql_session:
        image = SessionImageRepository(sql_session).get("image-1")
    assert image.current_relative_path == "ignored/corrupted/capture.jpg"


def test_dry_run_does_not_create_process_or_move_files(
    configured_workspace: Path, make_corrupted_image
):
    _, source_path = _create_session_inventory(configured_workspace)
    make_corrupted_image(source_path)

    result = run(SessionCleanCorruptedInput(session_id=SESSION_ID, dry_run=True))

    assert result.process is None
    assert source_path.exists()
    assert result.dry_run is True
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        process = SessionProcessRepository(sql_session).get_optional(
            SESSION_ID, "clean_corrupted"
        )
    assert process is None


def test_run_rejects_symlinked_session_content_before_creating_process(
    configured_workspace: Path,
    make_corrupted_image,
    tmp_path: Path,
):
    _, source_path = _create_session_inventory(configured_workspace)
    linked_target = make_corrupted_image(tmp_path / "capture.jpg")
    source_path.symlink_to(linked_target)

    with pytest.raises(SessionProcessError, match="Symbolic links are not supported"):
        run(SessionCleanCorruptedInput(session_id=SESSION_ID, dry_run=True))

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        process = SessionProcessRepository(sql_session).get_optional(
            SESSION_ID, "clean_corrupted"
        )
    assert process is None
    assert source_path.is_symlink()
    assert linked_target.exists()


def test_run_rejects_ineligible_ingest_session(
    configured_workspace: Path, make_image
):
    _, source_path = _create_session_inventory(
        configured_workspace, ingest_status="in_progress"
    )
    make_image(source_path)

    with pytest.raises(SessionProcessError, match="ingestion must be completed"):
        run(SessionCleanCorruptedInput(session_id=SESSION_ID))


def test_run_rejects_untracked_supported_image(
    configured_workspace: Path, make_corrupted_image
):
    _, source_path = _create_session_inventory(configured_workspace)
    make_corrupted_image(source_path)
    make_corrupted_image(source_path.parent / "untracked.jpg")

    with pytest.raises(SessionProcessError, match="not tracked"):
        run(SessionCleanCorruptedInput(session_id=SESSION_ID))


def test_run_records_image_inspection_failure(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    _, source_path = _create_session_inventory(configured_workspace)
    make_image(source_path)
    _record_actual_image_content(configured_workspace, source_path)
    monkeypatch.setattr(
        managed_corrupted,
        "is_image_corrupted",
        lambda _: (_ for _ in ()).throw(OSError("cannot inspect image")),
    )

    result = run(SessionCleanCorruptedInput(session_id=SESSION_ID))

    assert result.files_failed == 1
    assert result.process is not None
    assert result.process.status == "completed_with_failures"
    assert source_path.is_file()
