import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from wv.core.files import is_allowed_image_file
from wv.core.images import (
    compute_image_exposure_metrics,
    is_image_overexposed,
    validate_exposure_thresholds,
)
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_overexposed_path
from wv.domain.session import SessionProcess
from wv.persistence.repositories import SessionImageRepository, SessionProcessRepository

from wv.persistence.sql_session import sql_session_scope

from ._shared import (
    ManagedSession,
    SessionProcessError,
    canonical_process_parameters,
    _exclusive_session_lock,
    _reconcile_moved_init_inventory,
    resolve_managed_session,
    resolve_process_parameters,
    utc_now,
    validate_process_parameters,
    validate_process_attempt,
)
from wv.workspace.workspace_config import load_processing_config

PROCESS_NAME = "clean_overexposed_ir"
OVEREXPOSED_STATE = "ignored/overexposed"

logger = get_logger(__name__)


@dataclass(frozen=True)
class SessionCleanOverexposedIrInput:
    session_id: str
    mean_threshold: float | None = None
    std_threshold: float | None = None
    high_level: int | None = None
    pct_high_threshold: float | None = None
    dry_run: bool = False
    recover: bool = False


@dataclass(frozen=True)
class SessionCleanOverexposedIrResult:
    session_id: str
    process: SessionProcess | None
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_overexposed: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass
class _CleanOverexposedIrSummary:
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_overexposed: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _parameters_json(input_data: SessionCleanOverexposedIrInput) -> str:
    return canonical_process_parameters(
        {
            "high_level": input_data.high_level,
            "mean_threshold": input_data.mean_threshold,
            "pct_high_threshold": input_data.pct_high_threshold,
            "std_threshold": input_data.std_threshold,
        },
    )


def _validate_input(input_data: SessionCleanOverexposedIrInput) -> None:
    validate_exposure_thresholds(
        input_data.mean_threshold,
        input_data.std_threshold,
        input_data.high_level,
        input_data.pct_high_threshold,
    )


def _resolve_input(
    managed_session: ManagedSession, input_data: SessionCleanOverexposedIrInput
) -> SessionCleanOverexposedIrInput:
    settings = load_processing_config()
    with sql_session_scope(managed_session.database_path) as sql_session:
        process = SessionProcessRepository(sql_session).get_optional(managed_session.session.id, PROCESS_NAME)
    values = resolve_process_parameters(
        process,
        PROCESS_NAME,
        {
            "mean_threshold": input_data.mean_threshold,
            "std_threshold": input_data.std_threshold,
            "high_level": input_data.high_level,
            "pct_high_threshold": input_data.pct_high_threshold,
        },
        {
            "mean_threshold": settings.overexposed_ir.mean_threshold,
            "std_threshold": settings.overexposed_ir.std_threshold,
            "high_level": settings.overexposed_ir.high_level,
            "pct_high_threshold": settings.overexposed_ir.pct_high_threshold,
        },
    )
    return replace(
        input_data,
        mean_threshold=float(values["mean_threshold"]),
        std_threshold=float(values["std_threshold"]),
        high_level=int(values["high_level"]),
        pct_high_threshold=float(values["pct_high_threshold"]),
    )


def _prepare_attempt(
    managed_session: ManagedSession,
    input_data: SessionCleanOverexposedIrInput,
    parameters_json: str,
) -> int:
    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            input_data.recover,
        )
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        return _reconcile_moved_init_inventory(
            managed_session,
            SessionImageRepository(sql_session),
            get_ignored_overexposed_path(managed_session.session_path),
            OVEREXPOSED_STATE,
            persist=not input_data.dry_run,
        )


def _start_attempt(
    managed_session: ManagedSession,
    input_data: SessionCleanOverexposedIrInput,
    parameters_json: str,
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
        return process_repository.start(
            managed_session.session.id,
            PROCESS_NAME,
            utc_now(),
            parameters_json=parameters_json,
        )


def _complete_attempt(
    managed_session: ManagedSession,
    result: _CleanOverexposedIrSummary,
    recovered_moves: int,
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        _reconcile_moved_init_inventory(
            managed_session,
            SessionImageRepository(sql_session),
            get_ignored_overexposed_path(managed_session.session_path),
            OVEREXPOSED_STATE,
            persist=True,
        )

        status = "completed_with_failures" if result.files_failed else "completed"
        return SessionProcessRepository(sql_session).complete(
            managed_session.session.id,
            PROCESS_NAME,
            status=status,
            completed_at=utc_now(),
            files_discovered=result.files_discovered + recovered_moves,
            files_processed=result.files_processed + recovered_moves,
            files_selected=result.files_overexposed + recovered_moves,
            files_moved=result.files_moved + recovered_moves,
            files_ignored=result.files_ignored,
            files_failed=result.files_failed,
        )


def _fail_attempt(managed_session: ManagedSession, error: Exception) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        SessionProcessRepository(sql_session).fail(
            managed_session.session.id,
            PROCESS_NAME,
            completed_at=utc_now(),
            failure_message=str(error),
        )


def _clean_overexposed_images(
    managed_session: ManagedSession, input_data: SessionCleanOverexposedIrInput
) -> _CleanOverexposedIrSummary:
    destination = get_ignored_overexposed_path(managed_session.session_path)
    result = _CleanOverexposedIrSummary(
        destination=destination, dry_run=input_data.dry_run
    )

    source_files = list(managed_session.init_path.iterdir())
    with get_progress() as progress:
        task = progress.add_task("Processing overexposed IR candidates", total=len(source_files))
        for file_path in source_files:
            result.files_discovered += 1
            try:
                if not file_path.is_file() or not is_allowed_image_file(file_path):
                    result.files_ignored += 1
                    continue
                metrics = compute_image_exposure_metrics(file_path, input_data.high_level)
                result.files_processed += 1
                if not is_image_overexposed(
                    metrics,
                    input_data.mean_threshold,
                    input_data.std_threshold,
                    input_data.pct_high_threshold,
                ):
                    result.files_ignored += 1
                    continue

                result.files_overexposed += 1
                if input_data.dry_run:
                    continue
                destination.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), destination / file_path.name)
                result.files_moved += 1
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to process overexposed IR candidate %s", file_path)
            finally:
                progress.update(task, advance=1)

    return result


def _result(
    managed_session: ManagedSession,
    process: SessionProcess | None,
    summary: _CleanOverexposedIrSummary,
) -> SessionCleanOverexposedIrResult:
    return SessionCleanOverexposedIrResult(
        session_id=managed_session.session.id,
        process=process,
        files_discovered=summary.files_discovered,
        files_processed=summary.files_processed,
        files_moved=summary.files_moved,
        files_overexposed=summary.files_overexposed,
        files_ignored=summary.files_ignored,
        files_failed=summary.files_failed,
        destination=summary.destination,
        dry_run=summary.dry_run,
    )


def run(
    input_data: SessionCleanOverexposedIrInput,
) -> SessionCleanOverexposedIrResult:
    """Run overexposed IR cleanup for an inventory-tracked workspace session.

    Args:
        input_data: Session identifier, exposure thresholds, and execution
            options.

    Returns:
        The managed cleanup counters and persisted process record. ``process``
        is ``None`` for dry runs because they do not mutate process state.

    Raises:
        SessionProcessError: If ordering, retry parameters, or inventory rules
            reject the operation.
        ValueError: If an exposure threshold is invalid.
    """
    managed_session = resolve_managed_session(input_data.session_id)
    input_data = _resolve_input(managed_session, input_data)
    _validate_input(input_data)
    parameters_json = _parameters_json(input_data)

    with _exclusive_session_lock(managed_session.session_path, input_data.dry_run):
        recovered_moves = _prepare_attempt(
            managed_session, input_data, parameters_json
        )

        if input_data.dry_run:
            return _result(
                managed_session, None, _clean_overexposed_images(managed_session, input_data)
            )

        _start_attempt(managed_session, input_data, parameters_json)
        try:
            summary = _clean_overexposed_images(managed_session, input_data)
            process = _complete_attempt(managed_session, summary, recovered_moves)
        except Exception as exc:
            try:
                _fail_attempt(managed_session, exc)
            except Exception:
                logger.exception("Unable to record failed session process %s", PROCESS_NAME)
            raise

    return _result(managed_session, process, summary)
