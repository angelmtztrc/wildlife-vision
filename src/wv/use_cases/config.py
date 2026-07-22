from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from wv.workspace.common import WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.workspace_config import (
    get_config_property,
    get_workspace_config_path,
    initialize_workspace_config,
    load_workspace_config,
    reset_config_property,
    set_config_property,
    validate_known_key,
    validate_workspace_config,
    write_workspace_config,
)


@dataclass(frozen=True)
class ConfigValueResult:
    key: str
    value: Any


@dataclass(frozen=True)
class ConfigPathResult:
    path: Path


def _require_workspace_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")
    return workspace_path


def run_init() -> ConfigPathResult:
    workspace_path = _require_workspace_path()
    config_path = initialize_workspace_config(workspace_path)
    return ConfigPathResult(path=config_path)


def run_get(key: str) -> ConfigValueResult:
    validate_known_key(key)
    value = load_workspace_config()
    property_value = get_config_property(value, key)

    if property_value is None:
        raise WorkspaceError(f"Workspace config key is not set: {key}")

    return ConfigValueResult(key=key, value=property_value)


def run_set(key: str, raw_value: str) -> ConfigValueResult:
    validate_known_key(key)
    workspace_path = _require_workspace_path()
    value = load_workspace_config()
    parsed_value = yaml.safe_load(raw_value)

    updated_value = set_config_property(value, key, parsed_value)
    validate_workspace_config(updated_value, workspace_path)
    write_workspace_config(updated_value)

    return ConfigValueResult(key=key, value=get_config_property(updated_value, key))


def run_reset(key: str) -> ConfigValueResult:
    validate_known_key(key)
    workspace_path = _require_workspace_path()
    value = load_workspace_config()

    updated_value = reset_config_property(value, key, workspace_path)
    validate_workspace_config(updated_value, workspace_path)
    write_workspace_config(updated_value)

    return ConfigValueResult(key=key, value=get_config_property(updated_value, key))


def run_validate() -> ConfigPathResult:
    workspace_path = _require_workspace_path()
    validate_workspace_config(load_workspace_config(), workspace_path)
    return ConfigPathResult(path=get_workspace_config_path())


def run_path() -> ConfigPathResult:
    return ConfigPathResult(path=get_workspace_config_path())
