from dataclasses import dataclass
from pathlib import Path

from wv.models import Device
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.session import session_scope
from wv.workspace.common import WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.workspace_config import get_workspace_database_path


@dataclass(frozen=True)
class DeviceInput:
    id: str
    name: str
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class DeviceUpdateInput:
    id: str
    name: str | None = None
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None


def _get_database_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    database_path = get_workspace_database_path(workspace_path)
    if not database_path.is_file():
        raise WorkspaceError(f"Workspace database file not found: {database_path}")

    return database_path


def run_create(input_data: DeviceInput) -> Device:
    with session_scope(_get_database_path()) as session:
        return DeviceRepository(session).create(
            Device(
                id=input_data.id,
                name=input_data.name,
                manufacturer=input_data.manufacturer,
                serial_number=input_data.serial_number,
                notes=input_data.notes,
            )
        )


def run_list() -> list[Device]:
    with session_scope(_get_database_path()) as session:
        return DeviceRepository(session).list()


def run_show(device_id: str) -> Device:
    with session_scope(_get_database_path()) as session:
        return DeviceRepository(session).get(device_id)


def run_update(input_data: DeviceUpdateInput) -> Device:
    updates = {
        key: value
        for key, value in {
            "name": input_data.name,
            "manufacturer": input_data.manufacturer,
            "serial_number": input_data.serial_number,
            "notes": input_data.notes,
        }.items()
        if value is not None
    }

    if not updates:
        raise WorkspaceError("At least one field must be provided for update.")

    with session_scope(_get_database_path()) as session:
        return DeviceRepository(session).update(input_data.id, updates)


__all__ = [
    "DeviceInput",
    "Device",
    "DeviceUpdateInput",
    "RecordAlreadyExistsError",
    "RecordNotFoundError",
    "run_create",
    "run_list",
    "run_show",
    "run_update",
]
