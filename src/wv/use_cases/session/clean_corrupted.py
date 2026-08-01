import shutil
from dataclasses import dataclass
from pathlib import Path

from wv.core.files import is_allowed_image_file
from wv.core.images import is_image_corrupted
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_corrupted_path
from wv.models import SessionProcess
from wv.persistence.repositories import SessionImageRepository, SessionProcessRepository
from wv.persistence.sql_session import sql_session_scope

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
    files_discovered: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_corrupted: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass
class _CleanCorruptedSummary:
    files_discovered: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_corrupted: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


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
    result: _CleanCorruptedSummary,
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


def _clean_corrupted_images(
    managed_session: ManagedSession, dry_run: bool
) -> _CleanCorruptedSummary:
    destination = get_ignored_corrupted_path(managed_session.session_path)
    result = _CleanCorruptedSummary(destination=destination, dry_run=dry_run)

    source_files = list(managed_session.init_path.iterdir())
    with get_progress() as progress:
        task = progress.add_task("Processing corrupted image candidates", total=len(source_files))
        for file_path in source_files:
            result.files_discovered += 1
            try:
                if not file_path.is_file() or not is_allowed_image_file(file_path):
                    result.files_ignored += 1
                    continue
                if not is_image_corrupted(file_path):
                    continue
                result.files_corrupted += 1
                if dry_run:
                    continue
                destination.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), destination / file_path.name)
                result.files_moved += 1
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to process corrupted image candidate %s", file_path)
            finally:
                progress.update(task, advance=1)

    return result


def _result(
    managed_session: ManagedSession,
    process: SessionProcess | None,
    summary: _CleanCorruptedSummary,
) -> SessionCleanCorruptedResult:
    return SessionCleanCorruptedResult(
        session_id=managed_session.session.id,
        process=process,
        files_discovered=summary.files_discovered,
        files_moved=summary.files_moved,
        files_ignored=summary.files_ignored,
        files_corrupted=summary.files_corrupted,
        files_failed=summary.files_failed,
        destination=summary.destination,
        dry_run=summary.dry_run,
    )


def run(input_data: SessionCleanCorruptedInput) -> SessionCleanCorruptedResult:
    """Run corrupted cleanup for an inventory-tracked workspace session.

    The operation validates the session lifecycle, performs corruption
    classification, reconciles deterministic file moves with the session
    inventory, and records one durable process attempt.

    Args:
        input_data: Session identifier and execution options.

    Returns:
        The managed cleanup counters and persisted process record. ``process``
        is ``None`` for dry runs because they do not mutate process state.

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
            return _result(managed_session, None, _clean_corrupted_images(managed_session, True))

        _start_attempt(managed_session, input_data.recover)
        try:
            summary = _clean_corrupted_images(managed_session, False)
            process = _complete_attempt(managed_session, summary, recovered_moves)
        except Exception as exc:
            try:
                _fail_attempt(managed_session, exc)
            except Exception:
                logger.exception("Unable to record failed session process %s", PROCESS_NAME)
            raise

    return _result(managed_session, process, summary)
