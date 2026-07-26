from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigDurabilityError,
    SdConfigError,
    get_sd_config_path,
    load_sd_config,
    remove_sd_config,
    resolve_sd_path,
    sd_config_matches,
    sd_operation_lock,
)
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from ._shared import SdError
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class SdClearInput:
    path: Path


@dataclass(frozen=True)
class SdClearResult:
    path: Path
    config_path: Path
    cleared_device_id: str


def _run(input_data: SdClearInput, database_path: Path, sd_path: Path) -> SdClearResult:
    config_path = get_sd_config_path(sd_path)
    config = load_sd_config(config_path)

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        shared.require_config_matches_database(device_repository, config, sd_path)
        shared.set_device_monitoring_site(device_repository, config.device_id, None)

    try:
        remove_sd_config(config_path)
    except SdConfigDurabilityError as exc:
        raise SdError(
            "SD config removal may not be durable. Remount the SD card and inspect its config "
            f"before running 'wv sd sync {sd_path}'."
        ) from exc
    except OSError as removal_error:
        if not sd_config_matches(config_path, config):
            raise SdError(
                "SD clear could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from removal_error
        try:
            with sql_session_scope(database_path) as sql_session:
                device_repository = DeviceRepository(sql_session)
                device = shared.get_existing_device(device_repository, config.device_id)
                if device.monitoring_site_id is None:
                    shared.set_device_monitoring_site(
                        device_repository,
                        config.device_id,
                        config.monitoring_site_id,
                    )
        except Exception as rollback_error:
            raise SdError(
                "SD clear could not restore the workspace database. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from rollback_error
        raise SdError(
            f"Failed to remove SD config at {config_path}; the database assignment was restored."
        ) from removal_error

    return SdClearResult(
        path=sd_path,
        config_path=config_path,
        cleared_device_id=config.device_id,
    )


def run(input_data: SdClearInput) -> SdClearResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            return _run(input_data, database_path, sd_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc
    except RecordNotFoundError as exc:
        raise shared.to_sd_error(exc) from exc
