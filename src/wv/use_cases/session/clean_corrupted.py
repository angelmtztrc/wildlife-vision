import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from wv.core.files import get_content_digest, is_allowed_image_file
from wv.core.logger import get_logger
from wv.core.session import get_ignored_corrupted_path
from wv.models import SessionImage, SessionProcess
from wv.persistence.repositories import SessionImageRepository, SessionProcessRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.clean.corrupted import CleanCorruptedInput, CleanCorruptedResult
from wv.use_cases.clean.corrupted import run as run_clean_corrupted

from ._shared import (
    ManagedSession,
    SessionProcessError,
    resolve_managed_session,
    utc_now,
    validate_process_attempt,
)

PROCESS_NAME = "clean_corrupted"
INIT_STATE = "init"
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


def _relative_path(session_path: Path, path: Path) -> str:
    return path.relative_to(session_path).as_posix()


@contextmanager
def _exclusive_process_lock(session_path: Path) -> Iterator[None]:
    lock_path = session_path / f".{PROCESS_NAME}.lock"
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SessionProcessError(
                f"Session process is already running: {PROCESS_NAME}"
            ) from exc

        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _reconcile_corrupted_inventory(
    managed_session: ManagedSession,
    repository: SessionImageRepository,
    *,
    persist: bool,
) -> int:
    destination_directory = get_ignored_corrupted_path(managed_session.session_path)
    images = repository.list_for_session(managed_session.session.id)
    relocated = 0

    for image in images:
        current_path = managed_session.session_path / image.current_relative_path
        if current_path.parent != managed_session.init_path:
            continue

        destination_path = destination_directory / current_path.name
        if current_path.exists():
            if destination_path.exists():
                raise SessionProcessError(
                    f"Ambiguous image inventory for {image.id}: both {current_path} "
                    f"and {destination_path} exist."
                )
            continue

        if not destination_path.is_file():
            raise SessionProcessError(
                f"Image inventory is inconsistent for {image.id}: neither "
                f"{current_path} nor {destination_path} exists."
            )

        if (
            destination_path.stat().st_size != image.content_size_bytes
            or get_content_digest(destination_path) != image.content_digest
        ):
            raise SessionProcessError(
                f"Destination does not match inventory content for {image.id}: "
                f"{destination_path}"
            )

        if persist:
            repository.relocate(
                image.id,
                _relative_path(managed_session.session_path, destination_path),
                CORRUPTED_STATE,
            )
        relocated += 1

    current_images = {
        image.current_relative_path: image
        for image in repository.list_for_session(managed_session.session.id)
    }
    for file_path in managed_session.init_path.iterdir():
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            continue

        relative_path = _relative_path(managed_session.session_path, file_path)
        image = current_images.get(relative_path)
        if image is None:
            raise SessionProcessError(
                f"Supported image is not tracked by the session inventory: {file_path}"
            )
        if image.state != INIT_STATE:
            raise SessionProcessError(
                f"Image inventory state must be {INIT_STATE!r} while stored in init: "
                f"{file_path}"
            )

    return relocated


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
        return _reconcile_corrupted_inventory(
            managed_session,
            SessionImageRepository(sql_session),
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
        _reconcile_corrupted_inventory(managed_session, image_repository, persist=True)

        status = "completed_with_failures" if result.files_failed else "completed"
        return SessionProcessRepository(sql_session).complete(
            managed_session.session.id,
            PROCESS_NAME,
            status=status,
            completed_at=utc_now(),
            files_discovered=result.files_discovered,
            files_processed=result.files_discovered - result.files_ignored,
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
    with _exclusive_process_lock(managed_session.session_path):
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
