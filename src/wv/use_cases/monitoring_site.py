from dataclasses import dataclass
from wv.models import MonitoringSite
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class MonitoringSiteInput:
    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class MonitoringSiteUpdateInput:
    id: str
    name: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


def run_create(input_data: MonitoringSiteInput) -> MonitoringSite:
    with sql_session_scope(require_workspace_database_path()) as sql_session:
        return MonitoringSiteRepository(sql_session).create(
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


def run_list() -> list[MonitoringSite]:
    with sql_session_scope(require_workspace_database_path()) as sql_session:
        return MonitoringSiteRepository(sql_session).list()


def run_show(site_id: str) -> MonitoringSite:
    with sql_session_scope(require_workspace_database_path()) as sql_session:
        return MonitoringSiteRepository(sql_session).get(site_id)


def run_update(input_data: MonitoringSiteUpdateInput) -> MonitoringSite:
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

    with sql_session_scope(require_workspace_database_path()) as sql_session:
        return MonitoringSiteRepository(sql_session).update(input_data.id, updates)


__all__ = [
    "MonitoringSiteInput",
    "MonitoringSite",
    "MonitoringSiteUpdateInput",
    "RecordAlreadyExistsError",
    "RecordNotFoundError",
    "run_create",
    "run_list",
    "run_show",
    "run_update",
]
