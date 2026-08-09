from dataclasses import dataclass
from typing import Any

from wv.workspace.common import WorkspaceError
from wv.workspace.schema import WORKSPACE_VERSION, get_known_keys

from . import _shared as shared


@dataclass(frozen=True)
class ListConfigInput:
    pass


@dataclass(frozen=True)
class ConfigListItem:
    key: str
    value: Any


@dataclass(frozen=True)
class ListConfigResult:
    items: list[ConfigListItem]


def run(input_data: ListConfigInput) -> ListConfigResult:
    value, _workspace_path = shared.load_validated_config_value()
    if value["workspace"]["version"] != WORKSPACE_VERSION:
        raise WorkspaceError(
            "Workspace config is version 1. Run 'wv workspace migrate'."
        )
    return ListConfigResult(
        items=[
            ConfigListItem(
                key=key,
                value=shared.get_required_config_property(value, key),
            )
            for key in get_known_keys()
        ]
    )
