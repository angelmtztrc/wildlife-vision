from dataclasses import dataclass
from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.monitoring_sites import MonitoringSiteRecord
from wv.persistence.monitoring_sites import (
    create_monitoring_site,
    get_monitoring_site,
    list_monitoring_sites,
    update_monitoring_site,
)
from wv.workspace.common import WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.workspace_config import get_workspace_database_path


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


def _get_database_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    database_path = get_workspace_database_path(workspace_path)
    if not database_path.is_file():
        raise WorkspaceError(f"Workspace database file not found: {database_path}")

    return database_path


def run_create(input_data: MonitoringSiteInput) -> MonitoringSiteRecord:
    return create_monitoring_site(
        _get_database_path(),
        MonitoringSiteRecord(
            id=input_data.id,
            name=input_data.name,
            description=input_data.description,
            latitude=input_data.latitude,
            longitude=input_data.longitude,
            elevation=input_data.elevation,
            notes=input_data.notes,
        ),
    )


def run_list() -> list[MonitoringSiteRecord]:
    return list_monitoring_sites(_get_database_path())


def run_show(site_id: str) -> MonitoringSiteRecord:
    return get_monitoring_site(_get_database_path(), site_id)


def run_update(input_data: MonitoringSiteUpdateInput) -> MonitoringSiteRecord:
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

    return update_monitoring_site(_get_database_path(), input_data.id, updates)


__all__ = [
    "MonitoringSiteInput",
    "MonitoringSiteRecord",
    "MonitoringSiteUpdateInput",
    "RecordAlreadyExistsError",
    "RecordNotFoundError",
    "run_create",
    "run_list",
    "run_show",
    "run_update",
]
