from dataclasses import dataclass
from typing import Any

import yaml

from wv.workspace.workspace_config import get_config_property, set_config_property

from . import _shared as shared


@dataclass(frozen=True)
class SetConfigValueInput:
    key: str
    raw_value: str


@dataclass(frozen=True)
class SetConfigValueResult:
    key: str
    value: Any


def run(input_data: SetConfigValueInput) -> SetConfigValueResult:
    shared.require_known_config_key(input_data.key)
    value, workspace_path = shared.load_validated_config_value()
    parsed_value = yaml.safe_load(input_data.raw_value)

    updated_value = set_config_property(value, input_data.key, parsed_value)
    shared.write_config_update(updated_value, workspace_path)

    return SetConfigValueResult(
        key=input_data.key,
        value=get_config_property(updated_value, input_data.key),
    )
