from dataclasses import dataclass

from wv.core.identifiers import normalize_catalog_identifier
from wv.domain.monitoring_area import MonitoringArea
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringAreaRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class CreateMonitoringAreaInput:
    name: str
    id: str | None = None
    description: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CreateMonitoringAreaResult:
    monitoring_area: MonitoringArea


def run(input_data: CreateMonitoringAreaInput) -> CreateMonitoringAreaResult:
    try:
        area_id = normalize_catalog_identifier(input_data.id or input_data.name)
    except ValueError as exc:
        raise shared.MonitoringAreaError(str(exc)) from exc
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            area = MonitoringAreaRepository(sql_session).create(
                MonitoringArea(
                    id=area_id,
                    name=input_data.name,
                    description=input_data.description,
                    notes=input_data.notes,
                )
            )
    except PersistenceError as exc:
        message = str(exc)
        if message.startswith("Monitoring area already exists:"):
            message += ". Provide --id to choose a different identifier."
        raise shared.MonitoringAreaError(message) from exc
    return CreateMonitoringAreaResult(monitoring_area=area)
