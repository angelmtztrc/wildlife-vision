from pathlib import Path
from typing import Any

import platformdirs
import yaml

APP_NAME = "wildlife-vision"
GLOBAL_CONFIG_NAME = "config.yml"


def get_global_config_dir() -> Path:
    return Path(platformdirs.user_config_path(APP_NAME, appauthor=False))


def get_global_config_file() -> Path:
    return get_global_config_dir() / GLOBAL_CONFIG_NAME


def load_global_config() -> dict[str, Any]:
    config_file = get_global_config_file()
    if not config_file.exists():
        return {}

    with config_file.open("r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle) or {}


def write_global_config(value: dict[str, Any]) -> Path:
    config_dir = get_global_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = get_global_config_file()
    with config_file.open("w", encoding="utf-8") as file_handle:
        yaml.safe_dump(value, file_handle, sort_keys=False)

    return config_file


def get_workspace_path() -> Path | None:
    value = load_global_config()
    workspace = value.get("workspace")
    if not isinstance(workspace, dict):
        return None

    path_value = workspace.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        return None

    return Path(path_value).expanduser().resolve()
