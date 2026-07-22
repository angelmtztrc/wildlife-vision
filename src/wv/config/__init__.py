from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_FILE = CONFIG_DIR / "setup.yml"
REPO_ROOT_MARKER = "pyproject.toml"
DEFAULT_ROOT_PATH = "./.wv"


@lru_cache
def load() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {}


def get_property(key: str, default=None) -> Any:
    value = load()
    for part in key.split("."):
        if not isinstance(value, dict):
            return default
        value = value.get(part)
    return default if value is None else value


@lru_cache
def get_repo_root() -> Path:
    for directory in (CONFIG_DIR, *CONFIG_DIR.parents):
        if (directory / REPO_ROOT_MARKER).exists():
            return directory

    raise FileNotFoundError(
        f"Repository root not found from configuration directory: {CONFIG_DIR}"
    )


def get_root_path() -> Path:
    root_value = get_property("paths.root", DEFAULT_ROOT_PATH)

    if not isinstance(root_value, str):
        raise TypeError("Configuration value 'paths.root' must be a string.")

    root_path = Path(root_value).expanduser()
    if root_path.is_absolute():
        return root_path

    return get_repo_root() / root_path


def get_device_ids() -> list[str]:
    devices = get_property("devices", [])
    return [device["id"] for device in devices if "id" in device]


def get_monitoring_sites_ids() -> list[str]:
    monitoring_sites = get_property("monitoring_sites", [])
    return [site["id"] for site in monitoring_sites if "id" in site]
