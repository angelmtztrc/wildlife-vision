from pathlib import Path

from wv.domain.session import IngestSession
from wv.persistence.repositories import SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session.list import ListSessionsInput, run as run_list
from wv.use_cases.session.status import SessionStatusInput, run as run_status
from wv.workspace.workspace_config import require_workspace_database_path


def test_session_discovery_uses_site_and_derived_area(configured_workspace: Path):
    session_id = "20260808_120000__SITE001"
    (configured_workspace / "sessions" / session_id / "init").mkdir(parents=True)
    with sql_session_scope(
        require_workspace_database_path(configured_workspace)
    ) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=session_id,
                monitoring_site_id="SITE001",
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at="2026-08-08T12:00:00+00:00",
                ingest_status="completed",
            )
        )

    listed = run_list(ListSessionsInput(monitoring_area_id="AREA001"))
    status = run_status(SessionStatusInput(session_id=session_id))

    assert [session.id for session in listed.items] == [session_id]
    assert status.monitoring_area_id == "AREA001"
