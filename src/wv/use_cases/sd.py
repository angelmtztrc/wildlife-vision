from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from wv.models import Deployment, Device
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import (
    DeploymentRepository,
    DeviceRepository,
    MonitoringSiteRepository,
)
from wv.persistence.session import session_scope
from wv.workspace.common import WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.workspace_config import get_workspace_database_path


class SdError(ValueError):
    pass


@dataclass(frozen=True)
class SdConfigRecord:
    device_id: str
    monitoring_site_id: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SdInitInput:
    path: Path
    device_id: str
    monitoring_site_id: str


@dataclass(frozen=True)
class SdUpdateInput:
    path: Path
    device_id: str | None = None
    monitoring_site_id: str | None = None


@dataclass(frozen=True)
class SdClearInput:
    path: Path


@dataclass(frozen=True)
class SdCommandResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


@dataclass(frozen=True)
class SdClearResult:
    path: Path
    config_path: Path
    cleared_device_id: str


def _get_database_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    database_path = get_workspace_database_path(workspace_path)
    if not database_path.is_file():
        raise WorkspaceError(f"Workspace database file not found: {database_path}")

    return database_path


def _resolve_sd_path(path: Path) -> Path:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        raise SdError(f"SD path does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise SdError(f"SD path is not a directory: {resolved_path}")
    return resolved_path


def _get_sd_config_path(path: Path) -> Path:
    return path / ".wv" / "config.yml"


def _load_sd_config(config_path: Path) -> SdConfigRecord:
    if not config_path.is_file():
        raise SdError(f"SD config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file_handle:
        value = yaml.safe_load(file_handle) or {}

    if not isinstance(value, dict):
        raise SdError("SD config file must contain a YAML mapping.")

    missing_keys = [
        key
        for key in ("device_id", "monitoring_site_id", "created_at", "updated_at")
        if not isinstance(value.get(key), str) or not value.get(key)
    ]
    if missing_keys:
        raise SdError(
            f"SD config file is missing required fields: {', '.join(missing_keys)}"
        )

    return SdConfigRecord(
        device_id=value["device_id"],
        monitoring_site_id=value["monitoring_site_id"],
        created_at=value["created_at"],
        updated_at=value["updated_at"],
    )


def _write_sd_config(config_path: Path, config: SdConfigRecord) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with config_path.open("w", encoding="utf-8") as file_handle:
        yaml.safe_dump(
            {
                "device_id": config.device_id,
                "monitoring_site_id": config.monitoring_site_id,
                "created_at": config.created_at,
                "updated_at": config.updated_at,
            },
            file_handle,
            sort_keys=False,
        )

    return config_path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_existing_device(repository: DeviceRepository, device_id: str) -> Device:
    return repository.get(device_id)


def _validate_monitoring_site_exists(
    repository: MonitoringSiteRepository, monitoring_site_id: str
) -> None:
    repository.get(monitoring_site_id)


def _set_device_monitoring_site(
    repository: DeviceRepository,
    device_id: str,
    monitoring_site_id: str | None,
) -> Device:
    return repository.update(device_id, {"monitoring_site_id": monitoring_site_id})


def _clear_assignment_if_matches(
    repository: DeviceRepository,
    device_id: str,
    monitoring_site_id: str,
) -> None:
    device = _get_existing_device(repository, device_id)
    if device.monitoring_site_id == monitoring_site_id:
        _set_device_monitoring_site(repository, device_id, None)


def _record_deployment(
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


def run_init(input_data: SdInitInput) -> SdCommandResult:
    database_path = _get_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    config_path = _get_sd_config_path(sd_path)

    if config_path.exists():
        raise SdError(
            f"SD config already exists at {config_path}. Use 'wv sd update' instead."
        )

    timestamp = _now_iso()
    config = SdConfigRecord(
        device_id=input_data.device_id,
        monitoring_site_id=input_data.monitoring_site_id,
        created_at=timestamp,
        updated_at=timestamp,
    )

    _write_sd_config(config_path, config)

    with session_scope(database_path) as session:
        device_repository = DeviceRepository(session)
        monitoring_site_repository = MonitoringSiteRepository(session)
        deployment_repository = DeploymentRepository(session)
        device = _get_existing_device(device_repository, input_data.device_id)
        _validate_monitoring_site_exists(
            monitoring_site_repository, input_data.monitoring_site_id
        )

        if device.monitoring_site_id is not None:
            raise SdError(
                f"Device '{device.id}' is already assigned to monitoring site '{device.monitoring_site_id}'. "
                "Use 'wv sd update' instead."
            )

        _set_device_monitoring_site(
            device_repository, device.id, input_data.monitoring_site_id
        )
        _record_deployment(
            deployment_repository,
            device.id,
            input_data.monitoring_site_id,
            sd_path,
            timestamp,
        )

    return SdCommandResult(path=sd_path, config_path=config_path, config=config)


def run_show(path: Path) -> SdCommandResult:
    sd_path = _resolve_sd_path(path)
    config_path = _get_sd_config_path(sd_path)
    config = _load_sd_config(config_path)
    return SdCommandResult(path=sd_path, config_path=config_path, config=config)


def run_update(input_data: SdUpdateInput) -> SdCommandResult:
    database_path = _get_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    config_path = _get_sd_config_path(sd_path)
    current_config = _load_sd_config(config_path)

    if input_data.device_id is None and input_data.monitoring_site_id is None:
        raise SdError("At least one field must be provided for update.")

    next_device_id = input_data.device_id or current_config.device_id
    next_monitoring_site_id = (
        input_data.monitoring_site_id or current_config.monitoring_site_id
    )

    timestamp = _now_iso()
    updated_config = SdConfigRecord(
        device_id=next_device_id,
        monitoring_site_id=next_monitoring_site_id,
        created_at=current_config.created_at,
        updated_at=timestamp,
    )

    with session_scope(database_path) as session:
        device_repository = DeviceRepository(session)
        monitoring_site_repository = MonitoringSiteRepository(session)
        deployment_repository = DeploymentRepository(session)
        next_device = _get_existing_device(device_repository, next_device_id)
        _validate_monitoring_site_exists(
            monitoring_site_repository, next_monitoring_site_id
        )

        if (
            next_device.id != current_config.device_id
            and next_device.monitoring_site_id is not None
        ):
            raise SdError(
                f"Device '{next_device.id}' is already assigned to monitoring site '{next_device.monitoring_site_id}'."
            )

        _clear_assignment_if_matches(
            device_repository,
            current_config.device_id,
            current_config.monitoring_site_id,
        )
        _set_device_monitoring_site(
            device_repository, next_device.id, next_monitoring_site_id
        )
        _record_deployment(
            deployment_repository,
            next_device.id,
            next_monitoring_site_id,
            sd_path,
            timestamp,
        )

    _write_sd_config(config_path, updated_config)

    return SdCommandResult(path=sd_path, config_path=config_path, config=updated_config)


def run_clear(input_data: SdClearInput) -> SdClearResult:
    database_path = _get_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    config_path = _get_sd_config_path(sd_path)
    config = _load_sd_config(config_path)

    with session_scope(database_path) as session:
        _clear_assignment_if_matches(
            DeviceRepository(session),
            config.device_id,
            config.monitoring_site_id,
        )

    config_path.unlink()

    return SdClearResult(
        path=sd_path,
        config_path=config_path,
        cleared_device_id=config.device_id,
    )


__all__ = [
    "RecordNotFoundError",
    "SdClearInput",
    "SdClearResult",
    "SdCommandResult",
    "SdConfigRecord",
    "SdError",
    "SdInitInput",
    "SdUpdateInput",
    "run_clear",
    "run_init",
    "run_show",
    "run_update",
]
