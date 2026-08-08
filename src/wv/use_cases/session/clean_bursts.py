from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from wv.core.bursts import (
    BurstCandidate,
    BurstReductionPlan,
    DEFAULT_BURST_GAP_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
    build_burst_reduction_plan,
    create_burst_candidate,
    validate_burst_thresholds,
)
from wv.core.display import display_file
from wv.core.files import get_content_digest, is_allowed_image_file, move_file_with_staged_copy
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_bursts_path
from wv.domain.session import SessionImage, SessionProcess, SessionProcessImagePlan
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessImagePlanRepository,
    SessionProcessRepository,
)
from wv.persistence.sql_session import sql_session_scope
from ._shared import (
    ManagedSession,
    SessionProcessError,
    _exclusive_session_lock,
    _relative_path,
    _resolve_session_path,
    canonical_process_parameters,
    resolve_managed_session,
    utc_now,
    validate_process_attempt,
    validate_process_parameters,
)

PROCESS_NAME = "clean_bursts"
BURSTS_STATE = "ignored/bursts"
ALGORITHM_VERSION = 1

logger = get_logger(__name__)


@dataclass(frozen=True)
class SessionCleanBurstsInput:
    session_id: str
    burst_gap_threshold: int = DEFAULT_BURST_GAP_THRESHOLD
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD
    dry_run: bool = False
    recover: bool = False


@dataclass(frozen=True)
class SessionCleanBurstsResult:
    session_id: str
    process: SessionProcess | None
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_bursts: int = 0
    files_reduced: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass
class _CleanBurstsSummary:
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_bursts: int = 0
    files_reduced: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass(frozen=True)
class _PlanningInput:
    candidates: list[BurstCandidate]
    files_discovered: int
    unsupported_files: int
    scan_failures: int


def _parameters_json(input_data: SessionCleanBurstsInput) -> str:
    return canonical_process_parameters(
        {
            "algorithm_version": ALGORITHM_VERSION,
            "burst_gap_threshold": input_data.burst_gap_threshold,
            "similarity_threshold": input_data.similarity_threshold,
        }
    )


def _load_planning_input(
    managed_session: ManagedSession,
    repository: SessionImageRepository,
    source_files: list[Path],
    on_file_scanned: Callable[[], None] | None = None,
) -> _PlanningInput:
    images = repository.list_for_session(managed_session.session.id)
    images_by_path = {image.current_relative_path: image for image in images}
    candidates: list[BurstCandidate] = []
    files_discovered = 0
    unsupported_files = 0
    scan_failures = 0

    for file_path in source_files:
        files_discovered += 1
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            unsupported_files += 1
            if on_file_scanned is not None:
                on_file_scanned()
            continue

        relative_path = _relative_path(managed_session.session_path, file_path)
        image = images_by_path.get(relative_path)
        if image is None:
            raise SessionProcessError(
                f"Supported image is not tracked by the session inventory: {file_path}"
            )
        if image.state != "init":
            raise SessionProcessError(
                "Image inventory state must be 'init' while stored in init: "
                f"{file_path}"
            )
        try:
            candidates.append(create_burst_candidate(image.id, file_path))
        except Exception:
            scan_failures += 1
            logger.exception("Failed to scan burst candidate %s", display_file(file_path))
        if on_file_scanned is not None:
            on_file_scanned()

    for image in images:
        current_path = _resolve_session_path(
            managed_session.session_path, image.current_relative_path
        )
        if current_path.parent != managed_session.init_path.resolve():
            continue
        if not current_path.is_file():
            raise SessionProcessError(
                f"Image inventory source is not a file for {image.id}: {current_path}"
            )

    return _PlanningInput(
        candidates=candidates,
        files_discovered=files_discovered,
        unsupported_files=unsupported_files,
        scan_failures=scan_failures,
    )


def _count_existing_plan_unsupported_entries(
    managed_session: ManagedSession,
    plans: list[SessionProcessImagePlan],
    repository: SessionImageRepository,
) -> int:
    images_by_path = {
        image.current_relative_path: image
        for image in repository.list_for_session(managed_session.session.id)
    }
    planned_image_ids = {plan.image_id for plan in plans}
    unsupported_files = 0
    for file_path in managed_session.init_path.iterdir():
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            unsupported_files += 1
            continue

        relative_path = _relative_path(managed_session.session_path, file_path)
        image = images_by_path.get(relative_path)
        if image is None or image.id not in planned_image_ids or image.state != "init":
            raise SessionProcessError(
                f"Supported image is not covered by the burst plan: {file_path}"
            )
    return unsupported_files


def _build_result(
    planning_input: _PlanningInput, plan: BurstReductionPlan, dry_run: bool
) -> _CleanBurstsSummary:
    kept = sum(1 for decision in plan.decisions if decision.decision == "keep")
    reduced = sum(1 for decision in plan.decisions if decision.decision == "move")
    return _CleanBurstsSummary(
        files_discovered=planning_input.files_discovered,
        files_processed=plan.processed,
        files_ignored=planning_input.unsupported_files + kept,
        files_bursts=plan.bursts,
        files_reduced=reduced,
        files_failed=planning_input.scan_failures + len(plan.failures),
        dry_run=dry_run,
    )


def _get_existing_plans(
    managed_session: ManagedSession,
    input_data: SessionCleanBurstsInput,
    parameters_json: str,
) -> tuple[SessionProcess | None, list[SessionProcessImagePlan]]:
    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            input_data.recover,
        )
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        return (
            existing,
            SessionProcessImagePlanRepository(sql_session).list_for_process(
                managed_session.session.id, PROCESS_NAME
            ),
        )


def _persist_new_plan(
    managed_session: ManagedSession,
    input_data: SessionCleanBurstsInput,
    parameters_json: str,
    plan: BurstReductionPlan,
) -> None:
    planned_at = utc_now()
    destination_directory = get_ignored_bursts_path(managed_session.session_path)
    persisted_plan = [
        SessionProcessImagePlan(
            session_id=managed_session.session.id,
            process_name=PROCESS_NAME,
            image_id=decision.candidate_id,
            decision=decision.decision,
            target_relative_path=(
                _relative_path(
                    managed_session.session_path, destination_directory / decision.path.name
                )
                if decision.decision == "move"
                else None
            ),
            planned_at=planned_at,
        )
        for decision in plan.decisions
    ]

    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            input_data.recover,
        )
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        process_repository.start(
            managed_session.session.id,
            PROCESS_NAME,
            utc_now(),
            parameters_json=parameters_json,
        )
        process_repository.set_bursts_count(
            managed_session.session.id, PROCESS_NAME, plan.bursts
        )
        SessionProcessImagePlanRepository(sql_session).create_many(persisted_plan)


def _record_planning_failure(
    managed_session: ManagedSession,
    input_data: SessionCleanBurstsInput,
    parameters_json: str,
    result: _CleanBurstsSummary,
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            input_data.recover,
        )
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        process_repository.start(
            managed_session.session.id,
            PROCESS_NAME,
            utc_now(),
            parameters_json=parameters_json,
        )
        return process_repository.fail(
            managed_session.session.id,
            PROCESS_NAME,
            completed_at=utc_now(),
            failure_message="Burst planning failed; no files were moved.",
            files_discovered=result.files_discovered,
            files_processed=result.files_processed,
            files_selected=0,
            files_moved=0,
            files_ignored=result.files_ignored,
            files_failed=result.files_failed,
            bursts_count=result.files_bursts,
        )


def _apply_plan(
    managed_session: ManagedSession,
    plans: list[SessionProcessImagePlan],
    result: _CleanBurstsSummary,
    on_plan_applied: Callable[[], None] | None = None,
) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        images = {
            image.id: image
            for image in SessionImageRepository(sql_session).list_for_session(
                managed_session.session.id
            )
        }

    for plan in plans:
        image = images.get(plan.image_id)
        if image is None:
            raise SessionProcessError(
                f"Burst plan references an unknown session image: {plan.image_id}"
            )
        source_path = _resolve_session_path(
            managed_session.session_path, image.current_relative_path
        )

        if plan.decision == "keep":
            if image.state != "init" or source_path.parent != managed_session.init_path.resolve():
                raise SessionProcessError(
                    f"Burst keep decision is inconsistent for {image.id}: {source_path}"
                )
            _require_inventory_match(source_path, image)
            if on_plan_applied is not None:
                on_plan_applied()
            continue

        if plan.decision != "move" or plan.target_relative_path is None:
            raise SessionProcessError(f"Invalid burst plan decision for {image.id}")

        destination_path = _resolve_session_path(
            managed_session.session_path, plan.target_relative_path
        )
        if destination_path.parent != get_ignored_bursts_path(
            managed_session.session_path
        ).resolve():
            raise SessionProcessError(
                f"Burst plan target is outside ignored/bursts: {destination_path}"
            )

        if image.current_relative_path == plan.target_relative_path:
            if image.state != BURSTS_STATE or not destination_path.is_file():
                raise SessionProcessError(
                    f"Burst move decision is inconsistent for {image.id}: {destination_path}"
                )
            if not _matches_inventory(destination_path, image):
                raise SessionProcessError(
                    f"Burst destination does not match inventory for {image.id}: "
                    f"{destination_path}"
                )
            result.files_moved += 1
            if on_plan_applied is not None:
                on_plan_applied()
            continue

        source_exists = source_path.exists()
        destination_exists = destination_path.exists()
        if source_exists and destination_exists:
            raise SessionProcessError(
                f"Burst move decision is ambiguous for {image.id}: both {source_path} "
                f"and {destination_path} exist."
            )
        if not source_exists and not destination_exists:
            raise SessionProcessError(
                f"Burst move decision is inconsistent for {image.id}: neither "
                f"{source_path} nor {destination_path} exists."
            )

        if destination_exists:
            if not destination_path.is_file() or not _matches_inventory(
                destination_path, image
            ):
                raise SessionProcessError(
                    f"Burst destination does not match inventory for {image.id}: "
                    f"{destination_path}"
                )
            if image.current_relative_path != plan.target_relative_path:
                with sql_session_scope(managed_session.database_path) as sql_session:
                    SessionImageRepository(sql_session).relocate(
                        image.id, plan.target_relative_path, BURSTS_STATE
                    )
            result.files_moved += 1
            if on_plan_applied is not None:
                on_plan_applied()
            continue

        if image.state != "init" or not source_path.is_file():
            raise SessionProcessError(
                f"Burst move source is invalid for {image.id}: {source_path}"
            )

        try:
            _require_inventory_match(source_path, image)
            source_digest = image.content_digest
            move_file_with_staged_copy(
                source_path,
                destination_path,
                verify=lambda staged_path: get_content_digest(staged_path) == source_digest,
            )
            with sql_session_scope(managed_session.database_path) as sql_session:
                SessionImageRepository(sql_session).relocate(
                    image.id, plan.target_relative_path, BURSTS_STATE
                )
            result.files_moved += 1
        except Exception:
            result.files_failed += 1
            logger.exception("Failed to move reduced burst image %s", display_file(source_path))
        if on_plan_applied is not None:
            on_plan_applied()


def _matches_inventory(path: Path, image: SessionImage) -> bool:
    return (
        path.stat().st_size == image.content_size_bytes
        and get_content_digest(path) == image.content_digest
    )


def _require_inventory_match(path: Path, image: SessionImage) -> None:
    if not path.is_file() or not _matches_inventory(path, image):
        raise SessionProcessError(
            f"Burst source does not match inventory for {image.id}: {path}"
        )


def _complete_process(
    managed_session: ManagedSession, result: _CleanBurstsSummary
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        status = "completed_with_failures" if result.files_failed else "completed"
        return SessionProcessRepository(sql_session).complete(
            managed_session.session.id,
            PROCESS_NAME,
            status=status,
            completed_at=utc_now(),
            files_discovered=result.files_discovered,
            files_processed=result.files_processed,
            files_selected=result.files_reduced,
            files_moved=result.files_moved,
            files_ignored=result.files_ignored,
            files_failed=result.files_failed,
            bursts_count=result.files_bursts,
        )


def _fail_process(managed_session: ManagedSession, error: Exception) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        SessionProcessRepository(sql_session).fail(
            managed_session.session.id,
            PROCESS_NAME,
            completed_at=utc_now(),
            failure_message=str(error),
        )


def _result(
    managed_session: ManagedSession,
    process: SessionProcess | None,
    summary: _CleanBurstsSummary,
) -> SessionCleanBurstsResult:
    return SessionCleanBurstsResult(
        session_id=managed_session.session.id,
        process=process,
        files_discovered=summary.files_discovered,
        files_processed=summary.files_processed,
        files_moved=summary.files_moved,
        files_ignored=summary.files_ignored,
        files_bursts=summary.files_bursts,
        files_reduced=summary.files_reduced,
        files_failed=summary.files_failed,
        destination=summary.destination,
        dry_run=summary.dry_run,
    )


def run(input_data: SessionCleanBurstsInput) -> SessionCleanBurstsResult:
    """Run deterministic, plan-backed burst cleanup for a workspace session.

    The complete burst decision plan is committed before the first file moves.
    Recovery replays that immutable plan and never recomputes a reduced cohort.

    Args:
        input_data: Session identifier, burst thresholds, and execution options.

    Returns:
        The managed burst-cleanup counters and process record. Dry runs return
        no process record.

    Raises:
        SessionProcessError: If lifecycle, plan, or inventory rules reject work.
        ValueError: If burst thresholds are outside the supported range.
    """
    validate_burst_thresholds(
        input_data.burst_gap_threshold, input_data.similarity_threshold
    )
    parameters_json = _parameters_json(input_data)
    managed_session = resolve_managed_session(input_data.session_id)

    with _exclusive_session_lock(managed_session.session_path, input_data.dry_run):
        existing_process, existing_plans = _get_existing_plans(
            managed_session, input_data, parameters_json
        )
        if existing_plans:
            with sql_session_scope(managed_session.database_path) as sql_session:
                unsupported_files = _count_existing_plan_unsupported_entries(
                    managed_session,
                    existing_plans,
                    SessionImageRepository(sql_session),
                )
            plan = BurstReductionPlan(
                decisions=(), failures=(), bursts=0, processed=len(existing_plans)
            )
            result = _CleanBurstsSummary(
                files_discovered=len(existing_plans) + unsupported_files,
                files_processed=len(existing_plans),
                files_ignored=unsupported_files
                + sum(1 for item in existing_plans if item.decision == "keep"),
                files_reduced=sum(1 for item in existing_plans if item.decision == "move"),
                files_bursts=existing_process.bursts_count if existing_process else 0,
                dry_run=input_data.dry_run,
            )
        else:
            source_files = list(managed_session.init_path.iterdir())
            with get_progress() as progress:
                scan_task = progress.add_task(
                    "Scanning burst candidates", total=len(source_files)
                )
                with sql_session_scope(managed_session.database_path) as sql_session:
                    planning_input = _load_planning_input(
                        managed_session,
                        SessionImageRepository(sql_session),
                        source_files,
                        on_file_scanned=lambda: progress.update(scan_task, advance=1),
                    )
                analysis_task = progress.add_task(
                    "Analyzing burst candidates",
                    total=len(planning_input.candidates),
                )
                plan = build_burst_reduction_plan(
                    planning_input.candidates,
                    input_data.burst_gap_threshold,
                    input_data.similarity_threshold,
                    on_candidate_processed=lambda: progress.update(
                        analysis_task, advance=1
                    ),
                )
            result = _build_result(planning_input, plan, input_data.dry_run)

        result.destination = get_ignored_bursts_path(managed_session.session_path)
        if result.files_failed:
            process = None
            if not input_data.dry_run:
                process = _record_planning_failure(
                    managed_session, input_data, parameters_json, result
                )
            return _result(managed_session, process, result)

        if input_data.dry_run:
            return _result(managed_session, None, result)

        if not existing_plans:
            _persist_new_plan(managed_session, input_data, parameters_json, plan)
            with sql_session_scope(managed_session.database_path) as sql_session:
                existing_plans = SessionProcessImagePlanRepository(
                    sql_session
                ).list_for_process(managed_session.session.id, PROCESS_NAME)
        else:
            with sql_session_scope(managed_session.database_path) as sql_session:
                SessionProcessRepository(sql_session).start(
                    managed_session.session.id,
                    PROCESS_NAME,
                    utc_now(),
                    parameters_json=parameters_json,
                )
                if existing_process is not None:
                    SessionProcessRepository(sql_session).set_bursts_count(
                        managed_session.session.id,
                        PROCESS_NAME,
                        existing_process.bursts_count,
                    )

        try:
            with get_progress() as progress:
                apply_task = progress.add_task(
                    "Applying burst cleanup plan", total=len(existing_plans)
                )
                _apply_plan(
                    managed_session,
                    existing_plans,
                    result,
                    on_plan_applied=lambda: progress.update(apply_task, advance=1),
                )
            process = _complete_process(managed_session, result)
        except Exception as exc:
            try:
                _fail_process(managed_session, exc)
            except Exception:
                logger.exception("Unable to record failed session process %s", PROCESS_NAME)
            raise

    return _result(managed_session, process, result)
