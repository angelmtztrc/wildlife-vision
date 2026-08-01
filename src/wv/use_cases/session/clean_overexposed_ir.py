import json
from dataclasses import dataclass

from wv.core.images import validate_exposure_thresholds
from wv.core.logger import get_logger
from wv.core.session import get_ignored_overexposed_path
from wv.models import SessionProcess
from wv.persistence.repositories import SessionImageRepository, SessionProcessRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.clean.overexposed_ir import (
    CleanOverexposedIrInput,
    CleanOverexposedIrResult,
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.use_cases.clean.overexposed_ir import run as run_clean_overexposed_ir

from ._shared import (
    ManagedSession,
    SessionProcessError,
    _exclusive_session_lock,
    _reconcile_moved_init_inventory,
    resolve_managed_session,
    utc_now,
    validate_process_attempt,
)

PROCESS_NAME = "clean_overexposed_ir"
OVEREXPOSED_STATE = "ignored/overexposed"

logger = get_logger(__name__)


@dataclass(frozen=True)
class SessionCleanOverexposedIrInput:
    session_id: str
    mean_threshold: float = DEFAULT_MEAN_THRESHOLD
    std_threshold: float = DEFAULT_STD_THRESHOLD
    high_level: int = DEFAULT_HIGH_LEVEL
    ptc_high_threshold: float = DEFAULT_PTC_HIGH_THRESHOLD
    dry_run: bool = False
    recover: bool = False


@dataclass(frozen=True)
class SessionCleanOverexposedIrResult:
    session_id: str
    process: SessionProcess | None
    clean_result: CleanOverexposedIrResult


def _parameters_json(input_data: SessionCleanOverexposedIrInput) -> str:
    return json.dumps(
        {
            "high_level": input_data.high_level,
            "mean_threshold": input_data.mean_threshold,
            "ptc_high_threshold": input_data.ptc_high_threshold,
            "std_threshold": input_data.std_threshold,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_existing_parameters(
    process: SessionProcess | None, parameters_json: str
) -> None:
    if process is None:
        return

    if process.parameters_json is None:
        raise SessionProcessError(
            f"Session process has no recorded parameters: {PROCESS_NAME}"
        )

    try:
        stored_parameters = json.loads(process.parameters_json)
    except json.JSONDecodeError as exc:
        raise SessionProcessError(
            f"Session process has invalid recorded parameters: {PROCESS_NAME}"
        ) from exc

    canonical_stored_parameters = json.dumps(
        stored_parameters, sort_keys=True, separators=(",", ":")
    )
    if canonical_stored_parameters != parameters_json:
        raise SessionProcessError(
            f"Session process retry must use the recorded parameters: {PROCESS_NAME}"
        )


def _validate_input(input_data: SessionCleanOverexposedIrInput) -> None:
    validate_exposure_thresholds(
        input_data.mean_threshold,
        input_data.std_threshold,
        input_data.high_level,
        input_data.ptc_high_threshold,
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
        _validate_existing_parameters(existing, parameters_json)
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
        _validate_existing_parameters(existing, parameters_json)
        return process_repository.start(
            managed_session.session.id,
            PROCESS_NAME,
            utc_now(),
            parameters_json=parameters_json,
        )


def _complete_attempt(
    managed_session: ManagedSession,
    result: CleanOverexposedIrResult,
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


def run(
    input_data: SessionCleanOverexposedIrInput,
) -> SessionCleanOverexposedIrResult:
    """Run overexposed IR cleanup for an inventory-tracked workspace session.

    Args:
        input_data: Session identifier, exposure thresholds, and execution
            options.

    Returns:
        The raw cleanup result and persisted process record. ``process`` is
        ``None`` for dry runs because they do not mutate process state.

    Raises:
        SessionProcessError: If ordering, retry parameters, or inventory rules
            reject the operation.
        ValueError: If an exposure threshold is invalid.
    """
    _validate_input(input_data)
    parameters_json = _parameters_json(input_data)
    managed_session = resolve_managed_session(input_data.session_id)

    with _exclusive_session_lock(managed_session.session_path, input_data.dry_run):
        recovered_moves = _prepare_attempt(
            managed_session, input_data, parameters_json
        )

        if input_data.dry_run:
            clean_result = run_clean_overexposed_ir(
                CleanOverexposedIrInput(
                    source=managed_session.init_path,
                    output=managed_session.session_path,
                    mean_threshold=input_data.mean_threshold,
                    std_threshold=input_data.std_threshold,
                    high_level=input_data.high_level,
                    ptc_high_threshold=input_data.ptc_high_threshold,
                    dry_run=True,
                )
            )
            return SessionCleanOverexposedIrResult(
                session_id=managed_session.session.id,
                process=None,
                clean_result=clean_result,
            )

        _start_attempt(managed_session, input_data, parameters_json)
        try:
            clean_result = run_clean_overexposed_ir(
                CleanOverexposedIrInput(
                    source=managed_session.init_path,
                    output=managed_session.session_path,
                    mean_threshold=input_data.mean_threshold,
                    std_threshold=input_data.std_threshold,
                    high_level=input_data.high_level,
                    ptc_high_threshold=input_data.ptc_high_threshold,
                )
            )
            process = _complete_attempt(managed_session, clean_result, recovered_moves)
        except Exception as exc:
            try:
                _fail_attempt(managed_session, exc)
            except Exception:
                logger.exception("Unable to record failed session process %s", PROCESS_NAME)
            raise

    return SessionCleanOverexposedIrResult(
        session_id=managed_session.session.id,
        process=process,
        clean_result=clean_result,
    )
