from dataclasses import dataclass, field

from wv.domain.session import INGEST_STATUSES
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import SessionProcessRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class ListSessionsInput:
    monitoring_area_id: str | None = None
    monitoring_site_id: str | None = None
    ingest_status: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class SessionListItem:
    id: str
    started_at: str
    monitoring_site_id: str
    ingest_status: str
    processing_status: str
    next_action: str | None
    next_process: str | None


@dataclass(frozen=True)
class ListSessionsResult:
    items: list[SessionListItem] = field(default_factory=list)


def run(input_data: ListSessionsInput) -> ListSessionsResult:
    if input_data.limit < 1:
        raise shared.SessionError("Session list limit must be at least 1.")
    if (
        input_data.ingest_status is not None
        and input_data.ingest_status not in INGEST_STATUSES
    ):
        expected = ", ".join(INGEST_STATUSES)
        raise shared.SessionError(
            f"Unknown ingest status: {input_data.ingest_status}. Expected one of: {expected}."
        )

    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            sessions = SessionRepository(sql_session).list(
                monitoring_area_id=input_data.monitoring_area_id,
                monitoring_site_id=input_data.monitoring_site_id,
                ingest_status=input_data.ingest_status,
                limit=None,
                newest_first=True,
            )
            processes = SessionProcessRepository(sql_session).list_for_sessions(
                [session.id for session in sessions]
            )
    except PersistenceError as exc:
        raise shared.to_session_error(exc) from exc

    processes_by_session_id = {session.id: [] for session in sessions}
    for process in processes:
        processes_by_session_id[process.session_id].append(process)

    items = []
    for session in sessions:
        processing_status = shared.derive_processing_status(
            session, processes_by_session_id[session.id]
        )
        items.append(
            SessionListItem(
                id=session.id,
                started_at=session.started_at,
                monitoring_site_id=session.monitoring_site_id,
                ingest_status=session.ingest_status,
                processing_status=processing_status.status,
                next_action=processing_status.next_action,
                next_process=processing_status.next_process,
            )
        )
    incomplete = [item for item in items if item.processing_status != "completed"]
    completed = [item for item in items if item.processing_status == "completed"]
    return ListSessionsResult(items=[*incomplete, *completed][: input_data.limit])
