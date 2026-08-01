from pathlib import Path

import pytest

import wv.use_cases.session.clean_bursts as managed_bursts
from wv.core.bursts import (
    BurstDecision,
    BurstPlanningFailure,
    BurstReductionPlan,
)
from wv.core.files import get_content_digest
from wv.models import IngestSession, SessionImage
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessImagePlanRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionProcessError
from wv.use_cases.session.clean_bursts import SessionCleanBurstsInput, run
from wv.workspace.workspace_config import require_workspace_database_path


SESSION_ID = "20240731_120000__HNT001"


def _create_session_inventory(workspace_path: Path, image_paths: list[Path]) -> Path:
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
                started_at="2026-08-01T12:00:00+00:00",
                ingest_status="completed",
            )
        )
        repository = SessionImageRepository(sql_session)
        for index, image_path in enumerate(image_paths, start=1):
            repository.create_or_replace_by_initial_path(
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
                    ingested_at="2026-08-01T12:00:00+00:00",
                )
            )
    return session_path


def _complete_overexposed_process(workspace_path: Path) -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_overexposed_ir",
            "2026-08-01T12:01:00+00:00",
            parameters_json="{}",
        )
        repository.complete(
            SESSION_ID,
            "clean_overexposed_ir",
            status="completed",
            completed_at="2026-08-01T12:02:00+00:00",
            files_discovered=0,
            files_processed=0,
            files_selected=0,
            files_moved=0,
            files_ignored=0,
            files_failed=0,
        )


def _make_images(configured_workspace: Path, make_image) -> list[Path]:
    init_path = configured_workspace / "sessions" / SESSION_ID / "init"
    return [
        make_image(
            init_path / f"20240731_12000{index}__SITE001__ABC23{index}.jpg",
            color=(255, 255, 255),
        )
        for index in range(3)
    ]


def _three_image_plan(candidates) -> BurstReductionPlan:
    return BurstReductionPlan(
        decisions=(
            BurstDecision(candidates[0].id, candidates[0].path, "keep"),
            BurstDecision(candidates[1].id, candidates[1].path, "move"),
            BurstDecision(candidates[2].id, candidates[2].path, "move"),
        ),
        failures=(),
        bursts=1,
        processed=3,
    )


def test_run_persists_plan_before_moving_and_updates_inventory(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    image_paths = _make_images(configured_workspace, make_image)
    session_path = _create_session_inventory(configured_workspace, image_paths)
    _complete_overexposed_process(configured_workspace)
    monkeypatch.setattr(
        managed_bursts,
        "build_burst_reduction_plan",
        lambda candidates, *_: _three_image_plan(candidates),
    )

    result = run(SessionCleanBurstsInput(session_id=SESSION_ID))

    assert result.process is not None
    assert result.process.status == "completed"
    assert result.process.files_selected == 2
    assert result.process.files_moved == 2
    assert result.files_discovered == 3
    assert result.files_bursts == 1
    assert result.files_reduced == 2
    assert result.files_moved == 2
    assert result.destination == session_path / "ignored" / "bursts"
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            SESSION_ID, "clean_bursts"
        )
        moved_image = SessionImageRepository(sql_session).get("image-2")

    assert len(plans) == 3
    assert {plan.decision for plan in plans} == {"keep", "move"}
    assert moved_image.current_relative_path == f"ignored/bursts/{image_paths[1].name}"
    assert (session_path / moved_image.current_relative_path).is_file()


def test_run_requires_overexposed_predecessor(configured_workspace: Path, make_image):
    image_paths = _make_images(configured_workspace, make_image)
    _create_session_inventory(configured_workspace, image_paths)

    with pytest.raises(SessionProcessError, match="requires clean_overexposed_ir"):
        run(SessionCleanBurstsInput(session_id=SESSION_ID))


def test_retry_reuses_persisted_plan_without_replanning(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    image_paths = _make_images(configured_workspace, make_image)
    _create_session_inventory(configured_workspace, image_paths)
    _complete_overexposed_process(configured_workspace)
    monkeypatch.setattr(
        managed_bursts,
        "build_burst_reduction_plan",
        lambda candidates, *_: _three_image_plan(candidates),
    )
    original_move = managed_bursts.move_file_with_staged_copy
    calls = 0

    def fail_second_move(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("temporary move failure")
        return original_move(*args, **kwargs)

    monkeypatch.setattr(managed_bursts, "move_file_with_staged_copy", fail_second_move)
    first_result = run(SessionCleanBurstsInput(session_id=SESSION_ID))

    assert first_result.process is not None
    assert first_result.process.status == "completed_with_failures"

    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        repository = SessionProcessRepository(sql_session)
        repository.start(
            SESSION_ID,
            "clean_bursts",
            "2026-08-01T12:03:00+00:00",
            parameters_json=first_result.process.parameters_json,
        )
        repository.set_bursts_count(SESSION_ID, "clean_bursts", 1)

    monkeypatch.setattr(
        managed_bursts,
        "move_file_with_staged_copy",
        original_move,
    )
    monkeypatch.setattr(
        managed_bursts,
        "build_burst_reduction_plan",
        lambda *args: pytest.fail("retry must reuse the persisted burst plan"),
    )
    retry_result = run(SessionCleanBurstsInput(session_id=SESSION_ID, recover=True))

    assert retry_result.process is not None
    assert retry_result.process.status == "completed"
    assert retry_result.process.files_moved == 2
    assert retry_result.process.bursts_count == 1


def test_planning_failure_moves_no_files(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    image_paths = _make_images(configured_workspace, make_image)
    _create_session_inventory(configured_workspace, image_paths)
    _complete_overexposed_process(configured_workspace)

    def failing_plan(candidates, *_):
        return BurstReductionPlan(
            decisions=tuple(
                BurstDecision(candidate.id, candidate.path, "keep")
                for candidate in candidates
            ),
            failures=(
                BurstPlanningFailure(
                    candidates[0].id, candidates[0].path, "cannot decode"
                ),
            ),
            bursts=1,
            processed=2,
        )

    monkeypatch.setattr(managed_bursts, "build_burst_reduction_plan", failing_plan)

    result = run(SessionCleanBurstsInput(session_id=SESSION_ID))

    assert result.files_failed == 1
    assert result.process is not None
    assert result.process.status == "failed"
    assert all(path.is_file() for path in image_paths)
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        process = SessionProcessRepository(sql_session).get(SESSION_ID, "clean_bursts")
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            SESSION_ID, "clean_bursts"
        )
    assert process.status == "failed"
    assert plans == []


def test_dry_run_does_not_create_plan_or_move_files(
    configured_workspace: Path, make_image, monkeypatch: pytest.MonkeyPatch
):
    image_paths = _make_images(configured_workspace, make_image)
    _create_session_inventory(configured_workspace, image_paths)
    _complete_overexposed_process(configured_workspace)
    monkeypatch.setattr(
        managed_bursts,
        "build_burst_reduction_plan",
        lambda candidates, *_: _three_image_plan(candidates),
    )

    result = run(SessionCleanBurstsInput(session_id=SESSION_ID, dry_run=True))

    assert result.process is None
    assert all(path.is_file() for path in image_paths)
    assert result.dry_run is True
    with sql_session_scope(require_workspace_database_path(configured_workspace)) as sql_session:
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            SESSION_ID, "clean_bursts"
        )
    assert plans == []
