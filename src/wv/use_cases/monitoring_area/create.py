from dataclasses import dataclass

from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class CreateMonitoringAreaInput:
    id: str
    name: str
    description: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CreateMonitoringAreaResult:
    monitoring_area: MonitoringArea


def run(input_data: CreateMonitoringAreaInput) -> CreateMonitoringAreaResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            area = MonitoringAreaRepository(sql_session).create(
                MonitoringArea(
                    id=input_data.id,
                    name=input_data.name,
                    description=input_data.description,
                    notes=input_data.notes,
                )
            )
    except PersistenceError as exc:
        raise shared.to_monitoring_area_error(exc) from exc
    return CreateMonitoringAreaResult(monitoring_area=area)
