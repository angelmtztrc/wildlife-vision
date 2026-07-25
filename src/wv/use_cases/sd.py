from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import yaml

from wv.models import Deployment, Device
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import (
    DeploymentRepository,
    DeviceRepository,
    MonitoringSiteRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path


class SdError(ValueError):
    pass


class _SdConfigDurabilityError(SdError):
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
class SdSyncInput:
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


@dataclass(frozen=True)
class SdSyncResult:
    path: Path
    config_path: Path
    config: SdConfigRecord
    database_updated: bool
    deployment_recorded: bool


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

    try:
        with config_path.open("r", encoding="utf-8") as file_handle:
            value = yaml.safe_load(file_handle) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SdError(f"Could not read SD config at {config_path}: {exc}") from exc

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


def read_config(path: Path) -> SdConfigRecord:
    sd_path = _resolve_sd_path(path)
    return _load_sd_config(_get_sd_config_path(sd_path))


def _write_sd_config(config_path: Path, config: SdConfigRecord) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_name(f".{config_path.name}.{uuid4().hex}.tmp")

    try:
        with temporary_path.open("w", encoding="utf-8") as file_handle:
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
            file_handle.flush()
            try:
                os.fsync(file_handle.fileno())
            except OSError as exc:
                raise SdError(f"Could not durably write SD config at {config_path}") from exc
        temporary_path.replace(config_path)
        try:
            _sync_directory(config_path.parent)
        except OSError as exc:
            raise _SdConfigDurabilityError(
                f"SD config at {config_path} was replaced but could not be durably committed."
            ) from exc
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return config_path


def _remove_sd_config(config_path: Path) -> None:
    config_path.unlink()
    try:
        _sync_directory(config_path.parent)
    except OSError as exc:
        raise _SdConfigDurabilityError(
            f"SD config at {config_path} was removed but could not be durably committed."
        ) from exc


def _sync_directory(directory_path: Path) -> None:
    directory_fd = os.open(directory_path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


@contextmanager
def _sd_operation_lock(sd_path: Path) -> Iterator[None]:
    lock_name = hashlib.sha256(os.fsencode(str(sd_path))).hexdigest()
    # Keep the lock off-card so database synchronization works with read-only media.
    lock_path = Path(tempfile.gettempdir()) / f"wildlife-vision-{lock_name}.lock"

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise SdError(f"Could not lock SD card at {sd_path}: {exc}") from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _config_matches(config_path: Path, expected_config: SdConfigRecord) -> bool:
    try:
        return _load_sd_config(config_path) == expected_config
    except SdError:
        return False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_existing_device(repository: DeviceRepository, device_id: str) -> Device:
    return repository.get(device_id)


def _validate_monitoring_site_exists(
    repository: MonitoringSiteRepository, monitoring_site_id: str
) -> None:
    repository.get(monitoring_site_id)


def _require_config_matches_database(
    repository: DeviceRepository,
    config: SdConfigRecord,
    sd_path: Path,
) -> Device:
    device = _get_existing_device(repository, config.device_id)
    if device.monitoring_site_id != config.monitoring_site_id:
        raise SdError(
            "SD card deployment does not match the workspace database. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        )
    return device


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


def _run_init(
    input_data: SdInitInput, database_path: Path, sd_path: Path
) -> SdCommandResult:
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

    with sql_session_scope(database_path) as sql_session:
        device = _get_existing_device(DeviceRepository(sql_session), input_data.device_id)
        _validate_monitoring_site_exists(
            MonitoringSiteRepository(sql_session), input_data.monitoring_site_id
        )
        if device.monitoring_site_id is not None:
            raise SdError(
                f"Device '{device.id}' is already assigned to monitoring site '{device.monitoring_site_id}'. "
                "Use 'wv sd update' instead."
            )

    try:
        _write_sd_config(config_path, config)
    except _SdConfigDurabilityError as exc:
        raise SdError(
            "SD initialization may have changed the card config. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        ) from exc
    try:
        with sql_session_scope(database_path) as sql_session:
            device_repository = DeviceRepository(sql_session)
            device = _get_existing_device(device_repository, input_data.device_id)
            _validate_monitoring_site_exists(
                MonitoringSiteRepository(sql_session), input_data.monitoring_site_id
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
                DeploymentRepository(sql_session),
                device.id,
                input_data.monitoring_site_id,
                sd_path,
                timestamp,
            )
    except Exception:
        if not _config_matches(config_path, config):
            raise SdError(
                "SD initialization could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            )
        try:
            _remove_sd_config(config_path)
        except _SdConfigDurabilityError as rollback_error:
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

    return SdCommandResult(path=sd_path, config_path=config_path, config=config)


def run_show(path: Path) -> SdCommandResult:
    sd_path = _resolve_sd_path(path)
    config_path = _get_sd_config_path(sd_path)
    config = read_config(sd_path)
    return SdCommandResult(path=sd_path, config_path=config_path, config=config)


def _run_update(
    input_data: SdUpdateInput, database_path: Path, sd_path: Path
) -> SdCommandResult:
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

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        monitoring_site_repository = MonitoringSiteRepository(sql_session)
        _require_config_matches_database(device_repository, current_config, sd_path)
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

    if (
        next_device_id == current_config.device_id
        and next_monitoring_site_id == current_config.monitoring_site_id
    ):
        raise SdError("SD config already matches the requested device and monitoring site.")

    try:
        _write_sd_config(config_path, updated_config)
    except _SdConfigDurabilityError as exc:
        raise SdError(
            "SD update may have changed the card config. "
            f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
        ) from exc
    try:
        with sql_session_scope(database_path) as sql_session:
            device_repository = DeviceRepository(sql_session)
            monitoring_site_repository = MonitoringSiteRepository(sql_session)
            _require_config_matches_database(device_repository, current_config, sd_path)
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
                DeploymentRepository(sql_session),
                next_device.id,
                next_monitoring_site_id,
                sd_path,
                timestamp,
            )
    except Exception:
        if not _config_matches(config_path, updated_config):
            raise SdError(
                "SD update could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            )
        try:
            _write_sd_config(config_path, current_config)
        except Exception as rollback_error:
            raise SdError(
                "SD update could not be rolled back. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from rollback_error
        raise

    return SdCommandResult(path=sd_path, config_path=config_path, config=updated_config)


def _run_clear(
    input_data: SdClearInput, database_path: Path, sd_path: Path
) -> SdClearResult:
    config_path = _get_sd_config_path(sd_path)
    config = _load_sd_config(config_path)

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        _require_config_matches_database(device_repository, config, sd_path)
        _set_device_monitoring_site(device_repository, config.device_id, None)

    try:
        _remove_sd_config(config_path)
    except _SdConfigDurabilityError as exc:
        raise SdError(
            "SD config removal may not be durable. Remount the SD card and inspect its config "
            f"before running 'wv sd sync {sd_path}'."
        ) from exc
    except OSError as removal_error:
        if not _config_matches(config_path, config):
            raise SdError(
                "SD clear could not be safely rolled back because the card config changed. "
                f"Run 'wv sd sync {sd_path}' to synchronize the workspace from this SD card."
            ) from removal_error
        try:
            with sql_session_scope(database_path) as sql_session:
                device_repository = DeviceRepository(sql_session)
                device = _get_existing_device(device_repository, config.device_id)
                if device.monitoring_site_id is None:
                    _set_device_monitoring_site(
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


def _run_sync(
    input_data: SdSyncInput, database_path: Path, sd_path: Path
) -> SdSyncResult:
    config_path = _get_sd_config_path(sd_path)
    config = _load_sd_config(config_path)
    timestamp = _now_iso()

    with sql_session_scope(database_path) as sql_session:
        device_repository = DeviceRepository(sql_session)
        device = _get_existing_device(device_repository, config.device_id)
        _validate_monitoring_site_exists(
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

        _set_device_monitoring_site(
            device_repository, config.device_id, config.monitoring_site_id
        )
        _record_deployment(
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


def run_init(input_data: SdInitInput) -> SdCommandResult:
    database_path = require_workspace_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    with _sd_operation_lock(sd_path):
        return _run_init(input_data, database_path, sd_path)


def run_update(input_data: SdUpdateInput) -> SdCommandResult:
    database_path = require_workspace_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    with _sd_operation_lock(sd_path):
        return _run_update(input_data, database_path, sd_path)


def run_clear(input_data: SdClearInput) -> SdClearResult:
    database_path = require_workspace_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    with _sd_operation_lock(sd_path):
        return _run_clear(input_data, database_path, sd_path)


def run_sync(input_data: SdSyncInput) -> SdSyncResult:
    database_path = require_workspace_database_path()
    sd_path = _resolve_sd_path(input_data.path)
    with _sd_operation_lock(sd_path):
        return _run_sync(input_data, database_path, sd_path)


__all__ = [
    "RecordNotFoundError",
    "SdClearInput",
    "SdClearResult",
    "SdCommandResult",
    "SdConfigRecord",
    "SdError",
    "SdInitInput",
    "SdSyncInput",
    "SdSyncResult",
    "SdUpdateInput",
    "run_clear",
    "run_init",
    "run_show",
    "run_sync",
    "run_update",
]
