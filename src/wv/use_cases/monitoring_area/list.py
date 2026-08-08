from dataclasses import dataclass, field

from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class ListMonitoringAreasInput:
    pass


@dataclass(frozen=True)
class ListMonitoringAreasResult:
    items: list[MonitoringArea] = field(default_factory=list)


def run(input_data: ListMonitoringAreasInput) -> ListMonitoringAreasResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            items = MonitoringAreaRepository(sql_session).list()
    except PersistenceError as exc:
        raise shared.to_monitoring_area_error(exc) from exc
    return ListMonitoringAreasResult(items=items)
