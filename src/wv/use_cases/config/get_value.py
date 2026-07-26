from dataclasses import dataclass
from typing import Any

from . import _shared as shared


@dataclass(frozen=True)
class GetConfigValueInput:
    key: str


@dataclass(frozen=True)
class GetConfigValueResult:
    key: str
    value: Any


def run(input_data: GetConfigValueInput) -> GetConfigValueResult:
    shared.require_known_config_key(input_data.key)
    value, _workspace_path = shared.load_validated_config_value()
    property_value = shared.get_required_config_property(value, input_data.key)
    return GetConfigValueResult(key=input_data.key, value=property_value)
