from dataclasses import dataclass

from wv.domain.monitoring_site import MonitoringSite
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class UpdateMonitoringSiteInput:
    id: str
    name: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class UpdateMonitoringSiteResult:
    monitoring_site: MonitoringSite


def run(input_data: UpdateMonitoringSiteInput) -> UpdateMonitoringSiteResult:
    updates = {
        key: value
        for key, value in {
            "name": input_data.name,
            "description": input_data.description,
            "latitude": input_data.latitude,
            "longitude": input_data.longitude,
            "elevation": input_data.elevation,
            "notes": input_data.notes,
        }.items()
        if value is not None
    }

    if not updates:
        raise WorkspaceError("At least one field must be provided for update.")

    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            monitoring_site = MonitoringSiteRepository(sql_session).update(
                input_data.id, updates
            )
    except PersistenceError as exc:
        raise shared.to_monitoring_site_error(exc) from exc

    return UpdateMonitoringSiteResult(monitoring_site=monitoring_site)
