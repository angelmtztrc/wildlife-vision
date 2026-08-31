from dataclasses import dataclass

from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class UpdateMonitoringAreaInput:
    id: str
    name: str | None = None
    description: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class UpdateMonitoringAreaResult:
    monitoring_area: MonitoringArea


def run(input_data: UpdateMonitoringAreaInput) -> UpdateMonitoringAreaResult:
    updates = {
        key: value
        for key, value in {
            "name": input_data.name,
            "description": input_data.description,
            "notes": input_data.notes,
        }.items()
        if value is not None
    }
    if not updates:
        raise WorkspaceError("At least one field must be provided for update.")
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            area = MonitoringAreaRepository(sql_session).update(input_data.id, updates)
    except PersistenceError as exc:
        raise shared.to_monitoring_area_error(exc) from exc
    return UpdateMonitoringAreaResult(monitoring_area=area)
