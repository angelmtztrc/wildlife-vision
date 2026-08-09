from dataclasses import dataclass, field
from pathlib import Path

from wv.core.files import (
    SymlinkPathError,
    ensure_directory,
    ensure_not_symlink,
    ensure_tree_has_no_symlinks,
)
from wv.core.session import get_init_path, require_session_component
from wv.domain.session import IngestSession, SessionImageStateCount, SessionProcess
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import (
    MonitoringSiteRepository,
    SessionImageRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import (
    require_workspace_database_path,
    require_workspace_path,
)

from . import _shared as shared


@dataclass(frozen=True)
class SessionStatusInput:
    session_id: str


@dataclass(frozen=True)
class SessionStageStatus:
    name: str
    status: str = "not_started"
    attempt_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None
    failure_message: str | None = None
    files_discovered: int = 0
    files_processed: int = 0
    files_selected: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    bursts_count: int = 0
    parameters_json: str | None = None


@dataclass(frozen=True)
class SessionFilesystemStatus:
    session_path: Path
    init_path: Path
    status: str
    message: str | None = None


@dataclass(frozen=True)
class SessionStatusResult:
    session: IngestSession
    overall_status: str
    next_process: str | None
    next_action: str | None
    monitoring_area_id: str = ""
    stages: list[SessionStageStatus] = field(default_factory=list)
    inventory: list[SessionImageStateCount] = field(default_factory=list)
    filesystem: SessionFilesystemStatus | None = None


def _to_stage_status(process: SessionProcess) -> SessionStageStatus:
    return SessionStageStatus(
        name=process.process_name,
        status=process.status,
        attempt_count=process.attempt_count,
        started_at=process.started_at,
        completed_at=process.completed_at,
        failure_message=process.failure_message,
        files_discovered=process.files_discovered,
        files_processed=process.files_processed,
        files_selected=process.files_selected,
        files_moved=process.files_moved,
        files_ignored=process.files_ignored,
        files_failed=process.files_failed,
        bursts_count=process.bursts_count,
        parameters_json=process.parameters_json,
    )


def _inspect_filesystem(workspace_path: Path, session_id: str) -> SessionFilesystemStatus:
    sessions_path = workspace_path / "sessions"
    session_path = sessions_path / session_id
    init_path = get_init_path(session_path)

    try:
        require_session_component(session_id, "session ID")
    except ValueError as exc:
        return SessionFilesystemStatus(
            session_path=session_path,
            init_path=init_path,
            status="unsafe",
            message=str(exc),
        )

    try:
        ensure_not_symlink(sessions_path)
        ensure_tree_has_no_symlinks(session_path)
        ensure_directory(init_path)
    except FileNotFoundError as exc:
        return SessionFilesystemStatus(
            session_path=session_path,
            init_path=init_path,
            status="missing",
            message=f"Required session path not found: {exc}",
        )
    except NotADirectoryError as exc:
        return SessionFilesystemStatus(
            session_path=session_path,
            init_path=init_path,
            status="invalid",
            message=f"Required session path is not a directory: {exc}",
        )
    except SymlinkPathError as exc:
        return SessionFilesystemStatus(
            session_path=session_path,
            init_path=init_path,
            status="unsafe",
            message=str(exc),
        )
    except OSError as exc:
        return SessionFilesystemStatus(
            session_path=session_path,
            init_path=init_path,
            status="inaccessible",
            message=str(exc),
        )

    return SessionFilesystemStatus(
        session_path=session_path,
        init_path=init_path,
        status="available",
    )


def run(input_data: SessionStatusInput) -> SessionStatusResult:
    workspace_path = require_workspace_path()
    database_path = require_workspace_database_path(workspace_path)

    try:
        with sql_session_scope(database_path) as sql_session:
            session = SessionRepository(sql_session).get(input_data.session_id)
            monitoring_site = MonitoringSiteRepository(sql_session).get(
                session.monitoring_site_id
            )
            processes = SessionProcessRepository(sql_session).list_for_session(
                input_data.session_id
            )
            inventory = SessionImageRepository(sql_session).count_by_state_for_session(
                input_data.session_id
            )
    except PersistenceError as exc:
        raise shared.to_session_error(exc) from exc

    process_by_name = {process.process_name: process for process in processes}
    stages = [
        _to_stage_status(process_by_name[process_name])
        if process_name in process_by_name
        else SessionStageStatus(name=process_name)
        for process_name in shared.PROCESS_NAMES
    ]
    filesystem = _inspect_filesystem(workspace_path, session.id)
    processing_status = shared.derive_processing_status(session, processes)
    overall_status = processing_status.status
    next_process = processing_status.next_process
    next_action = processing_status.next_action
    if next_action is not None and filesystem.status != "available":
        overall_status = "filesystem_blocked"
        next_process = None
        next_action = None

    return SessionStatusResult(
        session=session,
        monitoring_area_id=monitoring_site.monitoring_area_id,
        overall_status=overall_status,
        next_process=next_process,
        next_action=next_action,
        stages=stages,
        inventory=inventory,
        filesystem=filesystem,
    )
