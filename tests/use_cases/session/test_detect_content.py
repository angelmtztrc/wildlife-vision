from pathlib import Path

import pytest

import wv.use_cases.session.detect_content as session_detection
from wv.core.files import get_content_digest
from wv.ml.megadetector import MlDetection, MlImageResult, ResolvedModel
from wv.domain.session import IngestSession, SessionImage
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessImagePlanRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionProcessError
from wv.use_cases.session.detect_content import SessionDetectContentInput, run
from wv.workspace.workspace_config import require_workspace_database_path


SESSION_ID = "20240801_120000__HNT001"


def _create_inventory(workspace_path: Path, paths: list[Path]) -> None:
    database_path = require_workspace_database_path(workspace_path)
    with sql_session_scope(database_path) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=SESSION_ID,
                monitoring_site_id="SITE001",
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at="2026-08-01T12:00:00+00:00",
                ingest_status="completed",
            )
        )
        repository = SessionImageRepository(sql_session)
        for index, path in enumerate(paths, start=1):
            repository.create_or_replace_by_initial_path(
                SessionImage(
                    id=f"image-{index}",
                    session_id=SESSION_ID,
                    source_relative_path=f"DCIM/{path.name}",
                    initial_relative_path=f"init/{path.name}",
                    current_relative_path=f"init/{path.name}",
                    state="init",
                    content_digest=get_content_digest(path),
                    content_size_bytes=path.stat().st_size,
                    captured_at="2024-08-01T12:00:00",
                    ingested_at="2026-08-01T12:00:00+00:00",
                )
            )


def _complete_bursts(workspace_path: Path) -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(SESSION_ID, "clean_bursts", "2026-08-01T12:01:00+00:00", "{}")
        repository.complete(
            SESSION_ID,
            "clean_bursts",
            status="completed",
            completed_at="2026-08-01T12:02:00+00:00",
            files_discovered=0,
            files_processed=0,
            files_selected=0,
            files_moved=0,
            files_ignored=0,
            files_failed=0,
        )


def _mock_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        session_detection,
        "resolve_model",
        lambda model: ResolvedModel(
            requested_model=model,
            resolved_path=Path("/tmp/model.pt"),
            content_digest="MODEL",
            content_size_bytes=1,
        ),
    )


def test_run_persists_detection_plan_and_updates_inventory(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    animal = make_image(init_path / "animal.jpg")
    empty = make_image(init_path / "empty.jpg")
    _create_inventory(configured_workspace, [animal, empty])
    _complete_bursts(configured_workspace)
    _mock_model(monkeypatch)
    monkeypatch.setattr(
        session_detection,
        "iter_evaluate_images",
        lambda **kwargs: [
            MlImageResult(animal, [MlDetection("animal", 0.91)]),
            MlImageResult(empty, []),
        ],
    )

    result = run(SessionDetectContentInput(session_id=SESSION_ID))

    assert result.process is not None
    assert result.process.status == "completed"
    assert result.files_animal == 1
    assert result.files_empty == 1
    assert result.files_moved == 2
    assert result.files_discovered == 2
    assert result.destination == configured_workspace / "sessions" / SESSION_ID / "detection"
    assert result.dry_run is False
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            SESSION_ID, "detect_content"
        )
        image = SessionImageRepository(sql_session).get("image-1")

    assert len(plans) == 2
    assert plans[0].decision_details_json is not None
    assert image.state == "detection/animal"
    assert image.content_digest != get_content_digest(animal) if animal.exists() else True
    assert (configured_workspace / "sessions" / SESSION_ID / image.current_relative_path).is_file()


def test_run_requires_burst_predecessor(configured_workspace: Path, make_image):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    path = make_image(init_path / "animal.jpg")
    _create_inventory(configured_workspace, [path])

    with pytest.raises(SessionProcessError, match="requires clean_bursts"):
        run(SessionDetectContentInput(session_id=SESSION_ID))


def test_dry_run_does_not_persist_plan_or_move_files(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    path = make_image(init_path / "animal.jpg")
    _create_inventory(configured_workspace, [path])
    _complete_bursts(configured_workspace)
    _mock_model(monkeypatch)
    monkeypatch.setattr(
        session_detection,
        "iter_evaluate_images",
        lambda **kwargs: [MlImageResult(path, [MlDetection("animal", 0.91)])],
    )

    result = run(SessionDetectContentInput(session_id=SESSION_ID, dry_run=True))

    assert result.process is None
    assert path.is_file()
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        assert SessionProcessImagePlanRepository(sql_session).list_for_process(
            SESSION_ID, "detect_content"
        ) == []


def test_recovery_replays_saved_plan_without_model(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    path = make_image(init_path / "animal.jpg")
    (init_path / "notes.txt").write_text("ignore")
    _create_inventory(configured_workspace, [path])
    _complete_bursts(configured_workspace)
    _mock_model(monkeypatch)
    monkeypatch.setattr(
        session_detection,
        "iter_evaluate_images",
        lambda **kwargs: [MlImageResult(path, [MlDetection("animal", 0.91)])],
    )
    first = run(SessionDetectContentInput(session_id=SESSION_ID, batch_size=32))

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "detect_content",
            "2026-08-01T12:03:00+00:00",
            first.process.parameters_json,
        )

    monkeypatch.setattr(
        session_detection,
        "resolve_model",
        lambda model: pytest.fail("recovery must not resolve the model"),
    )
    monkeypatch.setattr(
        session_detection,
        "iter_evaluate_images",
        lambda **kwargs: pytest.fail("recovery must not run inference"),
    )

    recovered = run(SessionDetectContentInput(session_id=SESSION_ID, recover=True))

    assert recovered.process is not None
    assert recovered.process.status == "completed"
    assert recovered.process.attempt_count == 3
    assert recovered.process.files_discovered == 2
    assert recovered.process.files_ignored == 1
