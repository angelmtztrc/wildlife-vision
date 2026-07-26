from pathlib import Path
from uuid import uuid4

from wv.models import Deployment, Device
from wv.persistence.repositories import (
    DeploymentRepository,
    DeviceRepository,
    MonitoringSiteRepository,
)
from wv.core.sd_config import SdConfigRecord


class SdError(ValueError):
    pass


def get_existing_device(repository: DeviceRepository, device_id: str) -> Device:
    return repository.get(device_id)


def validate_monitoring_site_exists(
    repository: MonitoringSiteRepository, monitoring_site_id: str
) -> None:
    repository.get(monitoring_site_id)


def require_config_matches_database(
    repository: DeviceRepository,
    config: SdConfigRecord,
    sd_path: Path,
) -> Device:
    device = get_existing_device(repository, config.device_id)
    if device.monitoring_site_id != config.monitoring_site_id:
        raise SdError(
            "SD card deployment does not match the workspace database. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        )
    return device


def set_device_monitoring_site(
    repository: DeviceRepository,
    device_id: str,
    monitoring_site_id: str | None,
) -> Device:
    return repository.update(device_id, {"monitoring_site_id": monitoring_site_id})


def clear_assignment_if_matches(
    repository: DeviceRepository,
    device_id: str,
    monitoring_site_id: str,
) -> None:
    device = get_existing_device(repository, device_id)
    if device.monitoring_site_id == monitoring_site_id:
        set_device_monitoring_site(repository, device_id, None)


def record_deployment(
    repository: DeploymentRepository,
    device_id: str,
    monitoring_site_id: str,
    sd_card_path: Path,
    timestamp: str,
) -> Deployment:
    return repository.create(
        Deployment(
            id=uuid4().hex,
            device_id=device_id,
            monitoring_site_id=monitoring_site_id,
            sd_card_path=str(sd_card_path),
            created_at=timestamp,
            updated_at=timestamp,
        ),
    )


def to_sd_error(exc: Exception) -> SdError:
    return SdError(str(exc))
