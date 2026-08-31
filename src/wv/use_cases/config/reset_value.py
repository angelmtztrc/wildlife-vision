from dataclasses import dataclass
from typing import Any

from wv.workspace.workspace_config import get_config_property, reset_config_property

from . import _shared as shared


@dataclass(frozen=True)
class ResetConfigValueInput:
    key: str


@dataclass(frozen=True)
class ResetConfigValueResult:
    key: str
    value: Any


def run(input_data: ResetConfigValueInput) -> ResetConfigValueResult:
    shared.require_known_config_key(input_data.key)
    value, workspace_path = shared.load_validated_config_value()

    updated_value = reset_config_property(value, input_data.key, workspace_path)
    shared.write_config_update(updated_value, workspace_path)

    return ResetConfigValueResult(
        key=input_data.key,
        value=get_config_property(updated_value, input_data.key),
    )
