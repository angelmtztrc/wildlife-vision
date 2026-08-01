import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from wv.core.files import (
    SymlinkPathError,
    ensure_directory,
    ensure_not_symlink,
    ensure_tree_has_no_symlinks,
    get_content_digest,
    is_allowed_image_file,
)
from wv.core.session import get_init_path
from wv.models import IngestSession, SessionProcess
from wv.persistence.database import initialize_database
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import SessionProcessRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import (
    require_workspace_database_path,
    require_workspace_path,
)

PROCESS_NAMES = (
    "clean_corrupted",
    "clean_overexposed_ir",
    "clean_bursts",
    "detect_content",
)
SUCCESSFUL_PROCESS_STATUSES = {"completed", "completed_with_failures"}


class SessionProcessError(ValueError):
    pass


@dataclass(frozen=True)
class ManagedSession:
    database_path: Path
    session: IngestSession
    session_path: Path
    init_path: Path


def utc_now() -> str:
    """Return the current UTC time in ISO 8601 format for persistence."""
    return datetime.now(UTC).isoformat()


def resolve_managed_session(session_id: str) -> ManagedSession:
    """Resolve and validate an ingested session in the active workspace.

    Args:
        session_id: Persisted ingest-session identifier to resolve.

    Returns:
        The active workspace database path, persisted session, and canonical
        filesystem paths for the managed session.

    Raises:
        SessionProcessError: If the session is unknown, not eligible for
            processing, or its directory is outside the active workspace.
        FileNotFoundError: If the session or initial-ingest directory is absent.
        NotADirectoryError: If a required session path is not a directory.
    """
    workspace_path = require_workspace_path()
    database_path = require_workspace_database_path(workspace_path)
    initialize_database(database_path)

    try:
        with sql_session_scope(database_path) as sql_session:
            session = SessionRepository(sql_session).get(session_id)
    except RecordNotFoundError as exc:
        raise SessionProcessError(str(exc)) from exc

    sessions_path = workspace_path / "sessions"
    session_path = sessions_path / session.id
    if session_path.parent != sessions_path:
        raise SessionProcessError(f"Invalid session ID: {session.id}")

    try:
        ensure_not_symlink(sessions_path)
        ensure_tree_has_no_symlinks(session_path)
    except (FileNotFoundError, NotADirectoryError, SymlinkPathError) as exc:
        raise SessionProcessError(str(exc)) from exc

    init_path = get_init_path(session_path)
    ensure_directory(init_path)

    if session.ingest_status not in SUCCESSFUL_PROCESS_STATUSES:
        raise SessionProcessError(
            "Session ingestion must be completed before managed processing can start. "
            f"Current status: {session.ingest_status}"
        )

    return ManagedSession(
        database_path=database_path,
        session=session,
        session_path=session_path,
        init_path=init_path,
    )


def validate_process_attempt(
    repository: SessionProcessRepository,
    session_id: str,
    process_name: str,
    recover: bool,
) -> SessionProcess | None:
    """Validate whether a managed process may start or retry.

    Args:
        repository: Repository using the caller-owned transaction.
        session_id: Session whose process is being validated.
        process_name: Process to start from ``PROCESS_NAMES``.
        recover: Whether a previous interrupted attempt may be recovered.

    Returns:
        The existing process record when present, otherwise ``None``.

    Raises:
        SessionProcessError: If ordering, completion, retry, or recovery rules
            do not permit another attempt.
    """
    try:
        process_index = PROCESS_NAMES.index(process_name)
    except ValueError as exc:
        raise SessionProcessError(f"Unknown session process: {process_name}") from exc

    if process_index > 0:
        predecessor_name = PROCESS_NAMES[process_index - 1]
        predecessor = repository.get_optional(session_id, predecessor_name)
        if predecessor is None or predecessor.status not in SUCCESSFUL_PROCESS_STATUSES:
            raise SessionProcessError(
                f"{process_name} requires {predecessor_name} to complete first."
            )

    existing = repository.get_optional(session_id, process_name)
    if existing is None:
        return None

    if existing.status == "completed":
        raise SessionProcessError(f"Session process already completed: {process_name}")

    if existing.status == "in_progress":
        if not recover:
            raise SessionProcessError(
                f"Session process is already in progress: {process_name}. "
                "Use --recover after confirming the prior command stopped."
            )
        return existing

    if existing.status in {"completed_with_failures", "failed"}:
        for successor_name in PROCESS_NAMES[process_index + 1 :]:
            if repository.get_optional(session_id, successor_name) is not None:
                raise SessionProcessError(
                    f"Session process cannot be retried after {successor_name} has started."
                )
        return existing

    raise SessionProcessError(
        f"Session process has an unsupported status: {existing.status}"
    )


def canonical_process_parameters(parameters: dict[str, object]) -> str:
    """Serialize process parameters into a stable JSON representation."""
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def validate_process_parameters(
    process: SessionProcess | None, parameters_json: str, process_name: str
) -> None:
    """Require an existing process retry to use its recorded parameters."""
    if process is None:
        return
    if process.parameters_json is None:
        raise SessionProcessError(
            f"Session process has no recorded parameters: {process_name}"
        )

    try:
        stored_parameters = json.loads(process.parameters_json)
    except json.JSONDecodeError as exc:
        raise SessionProcessError(
            f"Session process has invalid recorded parameters: {process_name}"
        ) from exc

    if canonical_process_parameters(stored_parameters) != parameters_json:
        raise SessionProcessError(
            f"Session process retry must use the recorded parameters: {process_name}"
        )


def _relative_path(session_path: Path, path: Path) -> str:
    return path.relative_to(session_path.resolve()).as_posix()


def _resolve_session_path(session_path: Path, relative_path: str) -> Path:
    resolved_session_path = session_path.resolve()
    resolved_path = (resolved_session_path / relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_session_path)
    except ValueError as exc:
        raise SessionProcessError(
            f"Session inventory path is outside the session: {relative_path}"
        ) from exc
    return resolved_path


@contextmanager
def _exclusive_session_lock(session_path: Path, dry_run: bool) -> Iterator[None]:
    if dry_run:
        yield
        return

    lock_path = session_path / ".wv-session-process.lock"
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SessionProcessError("Session processing is already running.") from exc

        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _reconcile_moved_init_inventory(
    managed_session: ManagedSession,
    repository: "SessionImageRepository",
    destination_directory: Path,
    destination_state: str,
    *,
    persist: bool,
) -> int:
    destination_directory = _resolve_session_path(
        managed_session.session_path,
        _relative_path(managed_session.session_path, destination_directory),
    )
    init_path = managed_session.init_path.resolve()
    relocated = 0

    for image in repository.list_for_session(managed_session.session.id):
        current_path = _resolve_session_path(
            managed_session.session_path, image.current_relative_path
        )
        if current_path.parent != init_path:
            continue

        destination_path = destination_directory / current_path.name
        if current_path.exists():
            if not current_path.is_file():
                raise SessionProcessError(
                    f"Image inventory source is not a file for {image.id}: {current_path}"
                )
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
                destination_state,
            )
        relocated += 1

    current_images = {
        image.current_relative_path: image
        for image in repository.list_for_session(managed_session.session.id)
    }
    for file_path in init_path.iterdir():
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            continue

        relative_path = _relative_path(managed_session.session_path, file_path)
        image = current_images.get(relative_path)
        if image is None:
            raise SessionProcessError(
                f"Supported image is not tracked by the session inventory: {file_path}"
            )
        if image.state != "init":
            raise SessionProcessError(
                "Image inventory state must be 'init' while stored in init: "
                f"{file_path}"
            )

    return relocated
