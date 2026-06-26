from pathlib import Path
from functools import lru_cache
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


def get(key: str, default=None) -> Any:
    config = load()
    keys = key.split(".")
    value = config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default
    return value if value is not None else default


def get_camera_locations_ids() -> list[str]:
    locations = get("camera_locations", [])
    return [loc["id"] for loc in locations if "id" in loc]
