from dataclasses import dataclass
from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.devices import DeviceRecord
from wv.persistence.devices import (
    create_device,
    get_device,
    list_devices,
    update_device,
)
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


def run_create(input_data: DeviceInput) -> DeviceRecord:
    return create_device(
        _get_database_path(),
        DeviceRecord(
            id=input_data.id,
            name=input_data.name,
            manufacturer=input_data.manufacturer,
            serial_number=input_data.serial_number,
            notes=input_data.notes,
        ),
    )


def run_list() -> list[DeviceRecord]:
    return list_devices(_get_database_path())


def run_show(device_id: str) -> DeviceRecord:
    return get_device(_get_database_path(), device_id)


def run_update(input_data: DeviceUpdateInput) -> DeviceRecord:
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

    return update_device(_get_database_path(), input_data.id, updates)


__all__ = [
    "DeviceInput",
    "DeviceRecord",
    "DeviceUpdateInput",
    "RecordAlreadyExistsError",
    "RecordNotFoundError",
    "run_create",
    "run_list",
    "run_show",
    "run_update",
]
