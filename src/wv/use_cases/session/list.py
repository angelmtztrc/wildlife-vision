from dataclasses import dataclass, field

from wv.domain.session import INGEST_STATUSES, IngestSession
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import SessionRepository
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
class ListSessionsResult:
    items: list[IngestSession] = field(default_factory=list)


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
                limit=input_data.limit,
                newest_first=True,
            )
    except PersistenceError as exc:
        raise shared.to_session_error(exc) from exc

    return ListSessionsResult(items=sessions)
