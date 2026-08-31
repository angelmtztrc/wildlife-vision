from dataclasses import dataclass

from wv.core.identifiers import normalize_catalog_identifier
from wv.domain.monitoring_site import MonitoringSite
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository, MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class CreateMonitoringSiteInput:
    monitoring_area_id: str
    name: str
    latitude: float
    longitude: float
    id: str | None = None
    description: str | None = None
    elevation: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CreateMonitoringSiteResult:
    monitoring_site: MonitoringSite


def run(input_data: CreateMonitoringSiteInput) -> CreateMonitoringSiteResult:
    if not -90 <= input_data.latitude <= 90:
        raise shared.MonitoringSiteError("Latitude must be between -90 and 90.")
    if not -180 <= input_data.longitude <= 180:
        raise shared.MonitoringSiteError("Longitude must be between -180 and 180.")
    try:
        site_id = normalize_catalog_identifier(input_data.id or input_data.name)
    except ValueError as exc:
        raise shared.MonitoringSiteError(str(exc)) from exc
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            MonitoringAreaRepository(sql_session).get(input_data.monitoring_area_id)
            monitoring_site = MonitoringSiteRepository(sql_session).create(
                MonitoringSite(
                    id=site_id,
                    monitoring_area_id=input_data.monitoring_area_id,
                    name=input_data.name,
                    description=input_data.description,
                    latitude=input_data.latitude,
                    longitude=input_data.longitude,
                    elevation=input_data.elevation,
                    notes=input_data.notes,
                )
            )
    except PersistenceError as exc:
        message = str(exc)
        if message.startswith("Monitoring site already exists:"):
            message += ". Provide --id to choose a different identifier."
        raise shared.MonitoringSiteError(message) from exc

    return CreateMonitoringSiteResult(monitoring_site=monitoring_site)
