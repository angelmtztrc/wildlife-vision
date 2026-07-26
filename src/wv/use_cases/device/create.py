from dataclasses import dataclass

from wv.models import Device
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class CreateDeviceInput:
    id: str
    name: str
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CreateDeviceResult:
    device: Device


def run(input_data: CreateDeviceInput) -> CreateDeviceResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            device = DeviceRepository(sql_session).create(
                Device(
                    id=input_data.id,
                    name=input_data.name,
                    manufacturer=input_data.manufacturer,
                    serial_number=input_data.serial_number,
                    notes=input_data.notes,
                )
            )
    except PersistenceError as exc:
        raise shared.to_device_error(exc) from exc

    return CreateDeviceResult(device=device)
