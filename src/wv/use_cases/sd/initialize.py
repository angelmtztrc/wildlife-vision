from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigDurabilityError,
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    now_iso,
    remove_sd_config,
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
class SdInitializeInput:
    path: Path
    device_id: str
    monitoring_site_id: str


@dataclass(frozen=True)
class SdInitializeResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


def _run(
    input_data: SdInitializeInput, database_path: Path, sd_path: Path
) -> SdInitializeResult:
    config_path = get_sd_config_path(sd_path)

    if config_path.exists():
        raise SdError(
            f"SD config already exists at {config_path}. Use 'wv sd update' instead."
        )

    timestamp = now_iso()
    config = SdConfigRecord(
        device_id=input_data.device_id,
        monitoring_site_id=input_data.monitoring_site_id,
        created_at=timestamp,
        updated_at=timestamp,
    )

    with sql_session_scope(database_path) as sql_session:
        device = shared.get_existing_device(
            DeviceRepository(sql_session), input_data.device_id
        )
        shared.validate_monitoring_site_exists(
            MonitoringSiteRepository(sql_session), input_data.monitoring_site_id
        )
        if device.monitoring_site_id is not None:
            raise SdError(
                f"Device '{device.id}' is already assigned to monitoring site '{device.monitoring_site_id}'. "
                "Use 'wv sd update' instead."
            )

    try:
        write_sd_config(config_path, config)
    except SdConfigDurabilityError as exc:
        raise SdError(
            "SD initialization may have changed the card config. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        ) from exc

    try:
        with sql_session_scope(database_path) as sql_session:
            device_repository = DeviceRepository(sql_session)
            device = shared.get_existing_device(device_repository, input_data.device_id)
            shared.validate_monitoring_site_exists(
                MonitoringSiteRepository(sql_session), input_data.monitoring_site_id
            )
            if device.monitoring_site_id is not None:
                raise SdError(
                    f"Device '{device.id}' is already assigned to monitoring site '{device.monitoring_site_id}'. "
                    "Use 'wv sd update' instead."
                )

            shared.set_device_monitoring_site(
                device_repository, device.id, input_data.monitoring_site_id
            )
            shared.record_deployment(
                DeploymentRepository(sql_session),
                device.id,
                input_data.monitoring_site_id,
                sd_path,
                timestamp,
            )
    except Exception:
        if not sd_config_matches(config_path, config):
            raise SdError(
                "SD initialization could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            )
        try:
            remove_sd_config(config_path)
        except SdConfigDurabilityError as rollback_error:
            raise SdError(
                "SD initialization could not confirm removal of the card config. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from rollback_error
        except OSError as rollback_error:
            raise SdError(
                "SD initialization could not be rolled back. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from rollback_error
        raise

    return SdInitializeResult(path=sd_path, config_path=config_path, config=config)


def run(input_data: SdInitializeInput) -> SdInitializeResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            return _run(input_data, database_path, sd_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc
    except RecordNotFoundError as exc:
        raise shared.to_sd_error(exc) from exc
