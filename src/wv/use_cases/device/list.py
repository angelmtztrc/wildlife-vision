from dataclasses import dataclass, field

from wv.models import Device
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class ListDevicesInput:
    pass


@dataclass(frozen=True)
class ListDevicesResult:
    items: list[Device] = field(default_factory=list)


def run(input_data: ListDevicesInput) -> ListDevicesResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            devices = DeviceRepository(sql_session).list()
    except PersistenceError as exc:
        raise shared.to_device_error(exc) from exc

    return ListDevicesResult(items=devices)
