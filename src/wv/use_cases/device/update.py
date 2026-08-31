from dataclasses import dataclass

from wv.domain.device import Device
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class UpdateDeviceInput:
    id: str
    name: str | None = None
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class UpdateDeviceResult:
    device: Device


def run(input_data: UpdateDeviceInput) -> UpdateDeviceResult:
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

    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            device = DeviceRepository(sql_session).update(input_data.id, updates)
    except PersistenceError as exc:
        raise shared.to_device_error(exc) from exc

    return UpdateDeviceResult(device=device)
