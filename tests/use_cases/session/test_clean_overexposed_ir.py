from pathlib import Path

import pytest

import wv.use_cases.session.clean_overexposed_ir as managed_overexposed
from wv.core.files import get_content_digest
from wv.models import IngestSession, SessionImage
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionProcessError
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrInput,
    run,
)
from wv.workspace.workspace_config import require_workspace_database_path


SESSION_ID = "20240731_120000__HNT001"
DEFAULT_PARAMETERS = (
    '{"high_level":220,"mean_threshold":200.0,'
    '"ptc_high_threshold":0.6,"std_threshold":25.0}'
)


def _create_session_inventory(
    workspace_path: Path, image_paths: list[Path]
) -> Path:
    database_path = require_workspace_database_path(workspace_path)
    session_path = workspace_path / "sessions" / SESSION_ID

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
                ingest_status="completed",
            )
        )
        image_repository = SessionImageRepository(sql_session)
        for index, image_path in enumerate(image_paths, start=1):
            image_repository.create_or_replace_by_initial_path(
                SessionImage(
                    id=f"image-{index}",
                    session_id=SESSION_ID,
                    source_relative_path=f"DCIM/{image_path.name}",
                    initial_relative_path=f"init/{image_path.name}",
                    current_relative_path=f"init/{image_path.name}",
                    state="init",
                    content_digest=get_content_digest(image_path),
                    content_size_bytes=image_path.stat().st_size,
                    captured_at="2024-07-31T12:00:00",
                    ingested_at="2026-07-31T12:00:00+00:00",
                )
            )

    return session_path


def _complete_corrupted_process(workspace_path: Path, status: str = "completed") -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_corrupted",
            "2026-07-31T12:01:00+00:00",
            parameters_json=None,
        )
        repository.complete(
            SESSION_ID,
            "clean_corrupted",
            status=status,
            completed_at="2026-07-31T12:02:00+00:00",
            files_discovered=0,
            files_processed=0,
            files_selected=0,
            files_moved=0,
            files_ignored=0,
            files_failed=0,
        )


def test_run_moves_overexposed_image_and_tracks_parameters(
    configured_workspace: Path, make_image
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    white_path = make_image(init_path / "white.jpg", color=(255, 255, 255))
    gray_path = make_image(init_path / "gray.jpg", color=(100, 100, 100))
    session_path = _create_session_inventory(configured_workspace, [white_path, gray_path])
    _complete_corrupted_process(configured_workspace)

    result = run(SessionCleanOverexposedIrInput(session_id=SESSION_ID))

    assert result.process is not None
    assert result.process.status == "completed"
    assert result.process.parameters_json == DEFAULT_PARAMETERS
    assert result.process.files_discovered == 2
    assert result.process.files_processed == 2
    assert result.process.files_selected == 1
    assert result.process.files_moved == 1
    assert result.files_discovered == 2
    assert result.files_processed == 2
    assert result.files_overexposed == 1
    assert result.files_moved == 1
    assert result.files_ignored == 1
    assert result.destination == session_path / "ignored" / "overexposed"
    assert result.dry_run is False
    assert not white_path.exists()
    assert gray_path.is_file()

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        white_image = SessionImageRepository(sql_session).get("image-1")
        gray_image = SessionImageRepository(sql_session).get("image-2")

    assert white_image.current_relative_path == "ignored/overexposed/white.jpg"
    assert white_image.state == "ignored/overexposed"
    assert gray_image.current_relative_path == "init/gray.jpg"
    assert gray_image.state == "init"
    assert (session_path / "ignored" / "overexposed" / "white.jpg").is_file()


def test_run_requires_corrupted_cleanup(configured_workspace: Path, make_image):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "gray.jpg", color=(100, 100, 100))
    _create_session_inventory(configured_workspace, [image_path])

    with pytest.raises(SessionProcessError, match="requires clean_corrupted"):
        run(SessionCleanOverexposedIrInput(session_id=SESSION_ID))


def test_run_accepts_partial_corrupted_cleanup(
    configured_workspace: Path, make_image
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "gray.jpg", color=(100, 100, 100))
    _create_session_inventory(configured_workspace, [image_path])
    _complete_corrupted_process(configured_workspace, status="completed_with_failures")

    result = run(SessionCleanOverexposedIrInput(session_id=SESSION_ID))

    assert result.process is not None
    assert result.process.status == "completed"


def test_run_rejects_changed_recovery_parameters(
    configured_workspace: Path, make_image
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "gray.jpg", color=(100, 100, 100))
    _create_session_inventory(configured_workspace, [image_path])
    _complete_corrupted_process(configured_workspace)

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        SessionProcessRepository(sql_session).start(
            SESSION_ID,
            "clean_overexposed_ir",
            "2026-07-31T12:03:00+00:00",
            parameters_json=DEFAULT_PARAMETERS,
        )

    with pytest.raises(SessionProcessError, match="recorded parameters"):
        run(
            SessionCleanOverexposedIrInput(
                session_id=SESSION_ID,
                mean_threshold=201.0,
                recover=True,
            )
        )


def test_dry_run_does_not_create_process_or_move_files(
    configured_workspace: Path, make_image
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "white.jpg", color=(255, 255, 255))
    _create_session_inventory(configured_workspace, [image_path])
    _complete_corrupted_process(configured_workspace)

    result = run(SessionCleanOverexposedIrInput(session_id=SESSION_ID, dry_run=True))

    assert result.process is None
    assert image_path.is_file()
    assert result.dry_run is True
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        process = SessionProcessRepository(sql_session).get_optional(
            SESSION_ID, "clean_overexposed_ir"
        )
    assert process is None


def test_run_recovers_interrupted_move(
    configured_workspace: Path, make_image
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "white.jpg", color=(255, 255, 255))
    session_path = _create_session_inventory(configured_workspace, [image_path])
    _complete_corrupted_process(configured_workspace)
    destination_path = session_path / "ignored" / "overexposed" / image_path.name
    destination_path.parent.mkdir(parents=True)
    image_path.replace(destination_path)

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        SessionProcessRepository(sql_session).start(
            SESSION_ID,
            "clean_overexposed_ir",
            "2026-07-31T12:03:00+00:00",
            parameters_json=DEFAULT_PARAMETERS,
        )

    result = run(
        SessionCleanOverexposedIrInput(session_id=SESSION_ID, recover=True)
    )

    assert result.process is not None
    assert result.process.status == "completed"
    assert result.process.attempt_count == 2
    assert result.process.files_moved == 1
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        image = SessionImageRepository(sql_session).get("image-1")
    assert image.current_relative_path == "ignored/overexposed/white.jpg"


def test_run_records_image_inspection_failure(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    image_path = make_image(init_path / "gray.jpg", color=(100, 100, 100))
    _create_session_inventory(configured_workspace, [image_path])
    _complete_corrupted_process(configured_workspace)
    monkeypatch.setattr(
        managed_overexposed,
        "compute_image_exposure_metrics",
        lambda *_: (_ for _ in ()).throw(OSError("cannot inspect image")),
    )

    result = run(SessionCleanOverexposedIrInput(session_id=SESSION_ID))

    assert result.files_failed == 1
    assert result.process is not None
    assert result.process.status == "completed_with_failures"
    assert image_path.is_file()
