import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import fcntl
import platformdirs
import yaml

from wv.core.files import SymlinkPathError, ensure_not_symlink
from wv.workspace.common import WorkspaceError

APP_NAME = "wildlife-vision"
GLOBAL_CONFIG_NAME = "config.yml"


def get_global_config_dir() -> Path:
    return Path(platformdirs.user_config_path(APP_NAME, appauthor=False))


def get_global_config_file() -> Path:
    return get_global_config_dir() / GLOBAL_CONFIG_NAME


def load_global_config() -> dict[str, Any]:
    config_file = get_global_config_file()
    try:
        ensure_not_symlink(config_file.parent)
        ensure_not_symlink(config_file)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not config_file.exists():
        return {}

    try:
        with config_file.open("r", encoding="utf-8") as file_handle:
            value = yaml.safe_load(file_handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise WorkspaceError(f"Unable to read global workspace config: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError("Global workspace config file must contain a YAML mapping.")
    return value


def write_global_config(value: dict[str, Any]) -> Path:
    config_dir = get_global_config_dir()
    config_file = get_global_config_file()
    temporary_path: Path | None = None
    try:
        ensure_not_symlink(config_dir)
        ensure_not_symlink(config_file)
        config_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=config_dir, prefix=f".{config_file.name}.", suffix=".tmp"
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(value, file_handle, sort_keys=False)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary_path, config_file)
        temporary_path = None
        try:
            directory_descriptor = os.open(config_dir, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            # Replacement is the commit point; reporting failure here would
            # incorrectly imply that the previous active workspace remains set.
            pass
    except (OSError, yaml.YAMLError, SymlinkPathError) as exc:
        raise WorkspaceError(f"Unable to write global workspace config: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return config_file


@contextmanager
def _lock_global_config(config_dir: Path):
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        lock_path = config_dir / f".{GLOBAL_CONFIG_NAME}.lock"
        ensure_not_symlink(lock_path)
        with lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (OSError, SymlinkPathError) as exc:
        raise WorkspaceError(f"Unable to lock global workspace config: {exc}") from exc


def set_workspace_path(workspace_path: Path) -> Path:
    canonical_workspace_path = workspace_path.expanduser().resolve()
    with _lock_global_config(get_global_config_dir()):
        value = load_global_config()
        workspace = value.get("workspace")
        updated_workspace = dict(workspace) if isinstance(workspace, dict) else {}
        updated_workspace["path"] = str(canonical_workspace_path)
        value["workspace"] = updated_workspace
        return write_global_config(value)


def get_workspace_path() -> Path | None:
    value = load_global_config()
    workspace = value.get("workspace")
    if not isinstance(workspace, dict):
        return None

    path_value = workspace.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().absolute()
