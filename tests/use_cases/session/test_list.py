from pathlib import Path

import pytest

from wv.domain.session import IngestSession
from wv.persistence.repositories import SessionRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.list import ListSessionsInput, run
from wv.workspace.workspace_config import require_workspace_database_path


def _create_session(
    workspace_path: Path,
    *,
    session_id: str,
    monitoring_site_id: str,
    started_at: str,
    ingest_status: str,
) -> None:
    with sql_session_scope(require_workspace_database_path(workspace_path)) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=session_id,
                monitoring_site_id=monitoring_site_id,
                source_path="/Volumes/SD",
                mode="copy",
                recursive=False,
                started_at=started_at,
                ingest_status=ingest_status,
            )
        )


def test_run_lists_newest_sessions_with_combined_filters(configured_workspace: Path):
    _create_session(
        configured_workspace,
        session_id="20260801_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-01T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260802_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-02T12:00:00+00:00",
        ingest_status="completed",
    )
    _create_session(
        configured_workspace,
        session_id="20260803_120000__SITE001",
        monitoring_site_id="SITE001",
        started_at="2026-08-03T12:00:00+00:00",
        ingest_status="failed",
    )

    result = run(
        ListSessionsInput(
            monitoring_site_id="SITE001",
            ingest_status="completed",
            limit=1,
        )
    )

    assert [session.id for session in result.items] == [
        "20260802_120000__SITE001"
    ]


@pytest.mark.parametrize(
    ("input_data", "message"),
    [
        (ListSessionsInput(limit=0), "limit"),
        (ListSessionsInput(ingest_status="unknown"), "Unknown ingest status"),
    ],
)
def test_run_rejects_invalid_filters(
    configured_workspace: Path,
    input_data: ListSessionsInput,
    message: str,
):
    with pytest.raises(SessionError, match=message):
        run(input_data)
