from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "setup.yml"


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


def get_monitoring_sites_ids() -> list[str]:
    monitoring_sites = get_property("monitoring_sites", [])
    return [site["id"] for site in monitoring_sites if "id" in site]
