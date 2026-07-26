from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigDurabilityError,
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    load_sd_config,
    now_iso,
    resolve_sd_path,
    sd_config_matches,
    sd_operation_lock,
    write_sd_config,
)
from wv.persistence.repositories import (
    DeploymentRepository,
    DeviceRepository,
    MonitoringSiteRepository,
)
from wv.persistence.common import RecordNotFoundError
from wv.persistence.sql_session import sql_session_scope
from . import _shared as shared
from ._shared import SdError
from wv.workspace.workspace_config import require_workspace_database_path


@dataclass(frozen=True)
class SdUpdateInput:
    path: Path
    device_id: str | None = None
    monitoring_site_id: str | None = None


@dataclass(frozen=True)
class SdUpdateResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


def _run(input_data: SdUpdateInput, database_path: Path, sd_path: Path) -> SdUpdateResult:
    config_path = get_sd_config_path(sd_path)
    current_config = load_sd_config(config_path)

    if input_data.device_id is None and input_data.monitoring_site_id is None:
        raise SdError("At least one field must be provided for update.")

    next_device_id = input_data.device_id or current_config.device_id
    next_monitoring_site_id = input_data.monitoring_site_id or current_config.monitoring_site_id

    timestamp = now_iso()
    updated_config = SdConfigRecord(
        device_id=next_device_id,
        monitoring_site_id=next_monitoring_site_id,
        created_at=current_config.created_at,
        updated_at=timestamp,
    )

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        monitoring_site_repository = MonitoringSiteRepository(sql_session)
        shared.require_config_matches_database(device_repository, current_config, sd_path)
        next_device = shared.get_existing_device(device_repository, next_device_id)
        shared.validate_monitoring_site_exists(
            monitoring_site_repository, next_monitoring_site_id
        )

        if next_device.id != current_config.device_id and next_device.monitoring_site_id is not None:
            raise SdError(
                f"Device '{next_device.id}' is already assigned to monitoring site '{next_device.monitoring_site_id}'."
            )

    if next_device_id == current_config.device_id and next_monitoring_site_id == current_config.monitoring_site_id:
        raise SdError("SD config already matches the requested device and monitoring site.")

    try:
        write_sd_config(config_path, updated_config)
    except SdConfigDurabilityError as exc:
        raise SdError(
            "SD update may have changed the card config. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        ) from exc

    try:
        with sql_session_scope(database_path) as sql_session:
            device_repository = DeviceRepository(sql_session)
            monitoring_site_repository = MonitoringSiteRepository(sql_session)
            shared.require_config_matches_database(device_repository, current_config, sd_path)
            next_device = shared.get_existing_device(device_repository, next_device_id)
            shared.validate_monitoring_site_exists(
                monitoring_site_repository, next_monitoring_site_id
            )
            if next_device.id != current_config.device_id and next_device.monitoring_site_id is not None:
                raise SdError(
                    f"Device '{next_device.id}' is already assigned to monitoring site '{next_device.monitoring_site_id}'."
                )

            shared.clear_assignment_if_matches(
                device_repository,
                current_config.device_id,
                current_config.monitoring_site_id,
            )
            shared.set_device_monitoring_site(
                device_repository, next_device.id, next_monitoring_site_id
            )
            shared.record_deployment(
                DeploymentRepository(sql_session),
                next_device.id,
                next_monitoring_site_id,
                sd_path,
                timestamp,
            )
    except Exception:
        if not sd_config_matches(config_path, updated_config):
            raise SdError(
                "SD update could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            )
        try:
            write_sd_config(config_path, current_config)
        except Exception as rollback_error:
            raise SdError(
                "SD update could not be rolled back. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from rollback_error
        raise

    return SdUpdateResult(path=sd_path, config_path=config_path, config=updated_config)


def run(input_data: SdUpdateInput) -> SdUpdateResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            return _run(input_data, database_path, sd_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc
    except RecordNotFoundError as exc:
        raise shared.to_sd_error(exc) from exc
