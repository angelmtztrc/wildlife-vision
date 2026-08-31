from dataclasses import dataclass

from wv.domain.device import Device
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class ShowDeviceInput:
    id: str


@dataclass(frozen=True)
class ShowDeviceResult:
    device: Device


def run(input_data: ShowDeviceInput) -> ShowDeviceResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            device = DeviceRepository(sql_session).get(input_data.id)
    except PersistenceError as exc:
        raise shared.to_device_error(exc) from exc

    return ShowDeviceResult(device=device)
