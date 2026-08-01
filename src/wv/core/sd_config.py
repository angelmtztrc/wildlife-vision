"""SD-card configuration file helpers."""

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

from wv.core.files import SymlinkPathError, ensure_not_symlink, ensure_tree_has_no_symlinks


class SdConfigError(ValueError):
    """Raised when SD-card configuration cannot be read or written."""


class SdConfigDurabilityError(SdConfigError):
    """Raised when an SD-card config mutation may not be durably committed."""


@dataclass(frozen=True)
class SdConfigRecord:
    """Configuration stored on an initialized SD card."""

    device_id: str
    monitoring_site_id: str
    created_at: str
    updated_at: str


def resolve_sd_path(path: Path) -> Path:
    """Resolve and validate a mounted SD-card path.

    Args:
        path: Candidate mounted SD-card directory.

    Returns:
        The expanded, absolute SD-card path.

    Raises:
        SdConfigError: If ``path`` does not exist or is not a directory.
    """
    expanded_path = path.expanduser()
    try:
        ensure_tree_has_no_symlinks(expanded_path)
    except (FileNotFoundError, NotADirectoryError, SymlinkPathError) as exc:
        raise SdConfigError(str(exc)) from exc
    return expanded_path.resolve()


def get_sd_config_path(path: Path) -> Path:
    """Return the package-local config path for an SD-card root.

    Args:
        path: Mounted SD-card root path.

    Returns:
        The ``.wv/config.yml`` path below ``path``.
    """
    return path / ".wv" / "config.yml"


def load_sd_config(config_path: Path) -> SdConfigRecord:
    """Load and validate an SD-card config file.

    Args:
        config_path: Full path to the SD-card YAML config file.

    Returns:
        Parsed SD-card configuration.

    Raises:
        SdConfigError: If the config file is missing, unreadable, malformed, or
            missing required string fields.
    """
    try:
        ensure_not_symlink(config_path.parent)
        ensure_not_symlink(config_path)
    except SymlinkPathError as exc:
        raise SdConfigError(str(exc)) from exc

    if not config_path.is_file():
        raise SdConfigError(f"SD config file not found: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as file_handle:
            value = yaml.safe_load(file_handle) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SdConfigError(f"Could not read SD config at {config_path}: {exc}") from exc

    if not isinstance(value, dict):
        raise SdConfigError("SD config file must contain a YAML mapping.")

    missing_keys = [
        key
        for key in ("device_id", "monitoring_site_id", "created_at", "updated_at")
        if not isinstance(value.get(key), str) or not value.get(key)
    ]
    if missing_keys:
        raise SdConfigError(
            f"SD config file is missing required fields: {', '.join(missing_keys)}"
        )

    return SdConfigRecord(
        device_id=value["device_id"],
        monitoring_site_id=value["monitoring_site_id"],
        created_at=value["created_at"],
        updated_at=value["updated_at"],
    )


def read_sd_config(path: Path) -> SdConfigRecord:
    """Resolve an SD-card root and load its config file.

    Args:
        path: Mounted SD-card root path.

    Returns:
        Parsed SD-card configuration.

    Raises:
        SdConfigError: If the SD-card path or config is invalid.
    """
    sd_path = resolve_sd_path(path)
    return load_sd_config(get_sd_config_path(sd_path))


def write_sd_config(config_path: Path, config: SdConfigRecord) -> Path:
    """Durably write an SD-card config file through a temporary replacement.

    Args:
        config_path: Full destination path for the YAML config file.
        config: Configuration to serialize.

    Returns:
        ``config_path`` after the replacement succeeds.

    Raises:
        SdConfigError: If the temporary file cannot be written or flushed.
        SdConfigDurabilityError: If the replacement happened but the directory
            sync could not be confirmed.

    Side Effects:
        Creates the config parent directory, writes a temporary file beside the
        config, atomically replaces the config, and fsyncs the parent directory.
    """
    try:
        ensure_not_symlink(config_path.parent)
        ensure_not_symlink(config_path)
    except SymlinkPathError as exc:
        raise SdConfigError(str(exc)) from exc

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
                raise SdConfigError(
                    f"Could not durably write SD config at {config_path}"
                ) from exc
        temporary_path.replace(config_path)
        try:
            _sync_directory(config_path.parent)
        except OSError as exc:
            raise SdConfigDurabilityError(
                f"SD config at {config_path} was replaced but could not be durably committed."
            ) from exc
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return config_path


def remove_sd_config(config_path: Path) -> None:
    """Remove an SD-card config file and fsync its parent directory.

    Args:
        config_path: Config file to remove.

    Raises:
        FileNotFoundError: If ``config_path`` does not exist.
        SdConfigDurabilityError: If the file was removed but directory sync
            could not be confirmed.
        OSError: If removing the config file fails.

    Side Effects:
        Deletes ``config_path`` and fsyncs its parent directory.
    """
    try:
        ensure_not_symlink(config_path.parent)
        ensure_not_symlink(config_path)
    except SymlinkPathError as exc:
        raise SdConfigError(str(exc)) from exc

    config_path.unlink()
    try:
        _sync_directory(config_path.parent)
    except OSError as exc:
        raise SdConfigDurabilityError(
            f"SD config at {config_path} was removed but could not be durably committed."
        ) from exc


def sd_config_matches(config_path: Path, expected_config: SdConfigRecord) -> bool:
    """Return whether an SD-card config matches an expected value.

    Args:
        config_path: Config file to inspect.
        expected_config: Expected configuration value.

    Returns:
        ``True`` when the config can be loaded and equals ``expected_config``;
        otherwise ``False``. Read and validation errors are intentionally
        treated as non-matches for rollback safety checks.
    """
    try:
        return load_sd_config(config_path) == expected_config
    except SdConfigError:
        return False


@contextmanager
def sd_operation_lock(sd_path: Path) -> Iterator[None]:
    """Lock operations for one SD-card path within the current machine.

    Args:
        sd_path: Resolved SD-card root path used to derive the lock file name.

    Yields:
        ``None`` while the exclusive lock is held.

    Raises:
        SdConfigError: If the lock file cannot be locked.

    Side Effects:
        Creates or opens a lock file in the system temporary directory. The lock
        is kept off-card so synchronization can work with read-only media.
    """
    lock_name = hashlib.sha256(os.fsencode(str(sd_path))).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"wildlife-vision-{lock_name}.lock"

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as exc:
            raise SdConfigError(f"Could not lock SD card at {sd_path}: {exc}") from exc
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def now_iso() -> str:
    """Return the current UTC timestamp formatted for SD-card config records.

    Returns:
        An ISO-8601 UTC timestamp string.
    """
    return datetime.now(UTC).isoformat()


def _sync_directory(directory_path: Path) -> None:
    directory_fd = os.open(directory_path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
