from pathlib import Path
from typing import Any

from wv.workspace.common import WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.workspace_config import (
    get_config_property,
    load_workspace_config,
    validate_known_key,
    validate_workspace_config,
    write_workspace_config,
)


def require_workspace_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")
    return workspace_path


def load_validated_config_value() -> tuple[dict[str, Any], Path]:
    workspace_path = require_workspace_path()
    return load_workspace_config(), workspace_path


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
