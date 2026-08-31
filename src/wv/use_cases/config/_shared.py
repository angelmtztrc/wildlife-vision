from pathlib import Path
from typing import Any

from wv.workspace.workspace_config import (
    get_config_property,
    load_workspace_config,
    require_workspace_path as require_active_workspace_path,
    validate_known_key,
    validate_workspace_config,
    write_workspace_config,
)
from wv.workspace.common import WorkspaceError


def require_workspace_path() -> Path:
    return require_active_workspace_path()


def load_validated_config_value() -> tuple[dict[str, Any], Path]:
    workspace_path = require_workspace_path()
    value = load_workspace_config()
    validate_workspace_config(value, workspace_path)
    return value, workspace_path


def write_config_update(value: dict[str, Any], workspace_path: Path) -> None:
    validate_workspace_config(value, workspace_path)
    write_workspace_config(value)


def require_known_config_key(key: str) -> None:
    validate_known_key(key)


def get_required_config_property(value: dict[str, Any], key: str) -> Any:
    property_value = get_config_property(value, key)
    if property_value is None:
        raise WorkspaceError(f"Workspace config key is not set: {key}")
    return property_value
