from dataclasses import dataclass

from wv.core.logger import get_logger
from wv.core.session import get_ignored_corrupted_path
from wv.models import SessionProcess
from wv.persistence.repositories import SessionImageRepository, SessionProcessRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.clean.corrupted import CleanCorruptedInput, CleanCorruptedResult
from wv.use_cases.clean.corrupted import run as run_clean_corrupted

from ._shared import (
    ManagedSession,
    SessionProcessError,
    _exclusive_session_lock,
    _reconcile_moved_init_inventory,
    resolve_managed_session,
    utc_now,
    validate_process_attempt,
)

PROCESS_NAME = "clean_corrupted"
CORRUPTED_STATE = "ignored/corrupted"

logger = get_logger(__name__)


@dataclass(frozen=True)
class SessionCleanCorruptedInput:
    session_id: str
    dry_run: bool = False
    recover: bool = False


@dataclass(frozen=True)
class SessionCleanCorruptedResult:
    session_id: str
    process: SessionProcess | None
    clean_result: CleanCorruptedResult


def _prepare_attempt(
    managed_session: ManagedSession, input_data: SessionCleanCorruptedInput
) -> int:
    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            input_data.recover,
        )
        return _reconcile_moved_init_inventory(
            managed_session,
            SessionImageRepository(sql_session),
            get_ignored_corrupted_path(managed_session.session_path),
            CORRUPTED_STATE,
            persist=not input_data.dry_run,
        )


def _start_attempt(
    managed_session: ManagedSession, recover: bool
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        process_repository = SessionProcessRepository(sql_session)
        validate_process_attempt(
            process_repository,
            managed_session.session.id,
            PROCESS_NAME,
            recover=recover,
        )
        return process_repository.start(
            managed_session.session.id,
            PROCESS_NAME,
            utc_now(),
            parameters_json=None,
        )


def _complete_attempt(
    managed_session: ManagedSession,
    result: CleanCorruptedResult,
    recovered_moves: int,
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        image_repository = SessionImageRepository(sql_session)
        _reconcile_moved_init_inventory(
            managed_session,
            image_repository,
            get_ignored_corrupted_path(managed_session.session_path),
            CORRUPTED_STATE,
            persist=True,
        )

        status = "completed_with_failures" if result.files_failed else "completed"
        return SessionProcessRepository(sql_session).complete(
            managed_session.session.id,
            PROCESS_NAME,
            status=status,
            completed_at=utc_now(),
            files_discovered=result.files_discovered + recovered_moves,
            files_processed=(result.files_discovered - result.files_ignored)
            + recovered_moves,
            files_selected=result.files_corrupted + recovered_moves,
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


def run(input_data: SessionCleanCorruptedInput) -> SessionCleanCorruptedResult:
    """Run corrupted cleanup for an inventory-tracked workspace session.

    The workflow validates the session lifecycle, reconciles deterministic file
    moves with the session inventory, and records one durable process attempt.
    The underlying corruption cleanup remains reusable without persistence.

    Args:
        input_data: Session identifier and execution options.

    Returns:
        The raw cleanup result and the persisted process record. ``process`` is
        ``None`` for dry runs because they do not mutate process state.

    Raises:
        SessionProcessError: If session lifecycle, ordering, or inventory rules
            reject the operation.
        FileNotFoundError: If required workspace session paths are absent.
        NotADirectoryError: If required workspace session paths are invalid.
    """
    managed_session = resolve_managed_session(input_data.session_id)
    with _exclusive_session_lock(managed_session.session_path, input_data.dry_run):
        recovered_moves = _prepare_attempt(managed_session, input_data)

        if input_data.dry_run:
            clean_result = run_clean_corrupted(
                CleanCorruptedInput(
                    source=managed_session.init_path,
                    output=managed_session.session_path,
                    dry_run=True,
                )
            )
            return SessionCleanCorruptedResult(
                session_id=managed_session.session.id,
                process=None,
                clean_result=clean_result,
            )

        _start_attempt(managed_session, input_data.recover)
        try:
            clean_result = run_clean_corrupted(
                CleanCorruptedInput(
                    source=managed_session.init_path,
                    output=managed_session.session_path,
                )
            )
            process = _complete_attempt(managed_session, clean_result, recovered_moves)
        except Exception as exc:
            try:
                _fail_attempt(managed_session, exc)
            except Exception:
                logger.exception("Unable to record failed session process %s", PROCESS_NAME)
            raise

    return SessionCleanCorruptedResult(
        session_id=managed_session.session.id,
        process=process,
        clean_result=clean_result,
    )
