from dataclasses import dataclass

from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class ShowMonitoringAreaInput:
    id: str


@dataclass(frozen=True)
class ShowMonitoringAreaResult:
    monitoring_area: MonitoringArea


def run(input_data: ShowMonitoringAreaInput) -> ShowMonitoringAreaResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            area = MonitoringAreaRepository(sql_session).get(input_data.id)
    except PersistenceError as exc:
        raise shared.to_monitoring_area_error(exc) from exc
    return ShowMonitoringAreaResult(monitoring_area=area)
