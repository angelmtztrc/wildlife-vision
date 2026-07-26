from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    load_sd_config,
    now_iso,
    resolve_sd_path,
    sd_operation_lock,
)
from wv.persistence.repositories import (
    DeploymentRepository,
    DeviceRepository,
    MonitoringSiteRepository,
)
from wv.persistence.common import RecordNotFoundError
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class SdSyncInput:
    path: Path


@dataclass(frozen=True)
class SdSyncResult:
    path: Path
    config_path: Path
    config: SdConfigRecord
    database_updated: bool
    deployment_recorded: bool


def _run(input_data: SdSyncInput, database_path: Path, sd_path: Path) -> SdSyncResult:
    config_path = get_sd_config_path(sd_path)
    config = load_sd_config(config_path)
    timestamp = now_iso()

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        device = shared.get_existing_device(device_repository, config.device_id)
        shared.validate_monitoring_site_exists(
            MonitoringSiteRepository(sql_session), config.monitoring_site_id
        )
        if device.monitoring_site_id == config.monitoring_site_id:
            return SdSyncResult(
                path=sd_path,
                config_path=config_path,
                config=config,
                database_updated=False,
                deployment_recorded=False,
            )

        shared.set_device_monitoring_site(
            device_repository, config.device_id, config.monitoring_site_id
        )
        shared.record_deployment(
            DeploymentRepository(sql_session),
            config.device_id,
            config.monitoring_site_id,
            sd_path,
            timestamp,
        )

    return SdSyncResult(
        path=sd_path,
        config_path=config_path,
        config=config,
        database_updated=True,
        deployment_recorded=True,
    )


def run(input_data: SdSyncInput) -> SdSyncResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            return _run(input_data, database_path, sd_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc
    except RecordNotFoundError as exc:
        raise shared.to_sd_error(exc) from exc
