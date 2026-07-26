from dataclasses import dataclass
from pathlib import Path

from wv.workspace.workspace_config import initialize_workspace_config

from ._shared import require_workspace_path


@dataclass(frozen=True)
class ConfigInitializeInput:
    pass


@dataclass(frozen=True)
class ConfigInitializeResult:
    path: Path


def run(input_data: ConfigInitializeInput) -> ConfigInitializeResult:
    workspace_path = require_workspace_path()
    config_path = initialize_workspace_config(workspace_path)
    return ConfigInitializeResult(path=config_path)
