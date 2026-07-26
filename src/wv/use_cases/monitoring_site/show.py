from dataclasses import dataclass

from wv.models import MonitoringSite
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class ShowMonitoringSiteInput:
    id: str


@dataclass(frozen=True)
class ShowMonitoringSiteResult:
    monitoring_site: MonitoringSite


def run(input_data: ShowMonitoringSiteInput) -> ShowMonitoringSiteResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            monitoring_site = MonitoringSiteRepository(sql_session).get(input_data.id)
    except PersistenceError as exc:
        raise shared.to_monitoring_site_error(exc) from exc

    return ShowMonitoringSiteResult(monitoring_site=monitoring_site)
