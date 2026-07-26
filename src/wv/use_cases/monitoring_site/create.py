from dataclasses import dataclass

from wv.models import MonitoringSite
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class CreateMonitoringSiteInput:
    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CreateMonitoringSiteResult:
    monitoring_site: MonitoringSite


def run(input_data: CreateMonitoringSiteInput) -> CreateMonitoringSiteResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            monitoring_site = MonitoringSiteRepository(sql_session).create(
                MonitoringSite(
                    id=input_data.id,
                    name=input_data.name,
                    description=input_data.description,
                    latitude=input_data.latitude,
                    longitude=input_data.longitude,
                    elevation=input_data.elevation,
                    notes=input_data.notes,
                )
            )
    except PersistenceError as exc:
        raise shared.to_monitoring_site_error(exc) from exc

    return CreateMonitoringSiteResult(monitoring_site=monitoring_site)
