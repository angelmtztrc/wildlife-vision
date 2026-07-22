from pathlib import Path
from typing import Any

import yaml

from wv.workspace.common import WORKSPACE_CONFIG_NAME, WORKSPACE_DATABASE_NAME, WORKSPACE_METADATA_DIRNAME, WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.schema import WORKSPACE_CONFIG_PROPERTIES, WORKSPACE_VERSION, build_default_config


def get_workspace_metadata_dir(workspace_path: Path) -> Path:
    return workspace_path / WORKSPACE_METADATA_DIRNAME


def get_workspace_config_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    return get_workspace_metadata_dir(workspace_path) / WORKSPACE_CONFIG_NAME


def get_workspace_database_path(workspace_path: Path) -> Path:
    return get_workspace_metadata_dir(workspace_path) / WORKSPACE_DATABASE_NAME


def load_workspace_config(config_file: Path | None = None) -> dict[str, Any]:
    resolved_config_file = config_file or get_workspace_config_path()
    if not resolved_config_file.exists():
        raise WorkspaceError(f"Workspace config file not found: {resolved_config_file}")

    with resolved_config_file.open("r", encoding="utf-8") as file_handle:
        value = yaml.safe_load(file_handle) or {}

    if not isinstance(value, dict):
        raise WorkspaceError("Workspace config file must contain a YAML mapping.")

    return value


def write_workspace_config(value: dict[str, Any], config_file: Path | None = None) -> Path:
    resolved_config_file = config_file or get_workspace_config_path()
    resolved_config_file.parent.mkdir(parents=True, exist_ok=True)

    with resolved_config_file.open("w", encoding="utf-8") as file_handle:
        yaml.safe_dump(value, file_handle, sort_keys=False)

    return resolved_config_file


def initialize_workspace_config(workspace_path: Path, config_file: Path | None = None) -> Path:
    return write_workspace_config(build_default_config(workspace_path), config_file=config_file)


def get_config_property(value: dict[str, Any], key: str, default: Any = None) -> Any:
    current_value: Any = value
    for part in key.split("."):
        if not isinstance(current_value, dict):
            return default
        current_value = current_value.get(part)
    return default if current_value is None else current_value


def set_config_property(value: dict[str, Any], key: str, property_value: Any) -> dict[str, Any]:
    current_value = value
    parts = key.split(".")

    for part in parts[:-1]:
        nested_value = current_value.get(part)
        if not isinstance(nested_value, dict):
            nested_value = {}
            current_value[part] = nested_value
        current_value = nested_value

    current_value[parts[-1]] = property_value
    return value


def reset_config_property(value: dict[str, Any], key: str, workspace_path: Path) -> dict[str, Any]:
    default_value = get_config_property(build_default_config(workspace_path), key)
    return set_config_property(value, key, default_value)


def validate_known_key(key: str) -> None:
    if key not in WORKSPACE_CONFIG_PROPERTIES:
        raise WorkspaceError(f"Unknown workspace config key: {key}")


def validate_workspace_config(value: dict[str, Any], workspace_path: Path) -> None:
    expected_workspace_path = workspace_path.resolve()
    expected_database_path = get_workspace_database_path(expected_workspace_path)

    for key, property_definition in WORKSPACE_CONFIG_PROPERTIES.items():
        property_value = get_config_property(value, key)

        if property_value is None:
            if property_definition.required:
                raise WorkspaceError(f"Missing required workspace config key: {key}")
            continue

        if not isinstance(property_value, property_definition.expected_type):
            raise WorkspaceError(
                f"Invalid workspace config value for {key}: expected {property_definition.expected_type.__name__}"
            )

    workspace_version = get_config_property(value, "workspace.version")
    if workspace_version != WORKSPACE_VERSION:
        raise WorkspaceError(
            f"Invalid workspace config value for workspace.version: expected {WORKSPACE_VERSION}"
        )

    workspace_path_value = get_config_property(value, "workspace.path")
    if not Path(workspace_path_value).is_absolute():
        raise WorkspaceError("Invalid workspace config value for workspace.path: expected absolute path")
    if Path(workspace_path_value).resolve() != expected_workspace_path:
        raise WorkspaceError("Invalid workspace config value for workspace.path: expected active workspace path")

    database_path_value = get_config_property(value, "database.path")
    if not Path(database_path_value).is_absolute():
        raise WorkspaceError("Invalid workspace config value for database.path: expected absolute path")
    if Path(database_path_value).resolve() != expected_database_path:
        raise WorkspaceError("Invalid workspace config value for database.path: expected workspace database path")
