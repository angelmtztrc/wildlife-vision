from dataclasses import dataclass
from pathlib import Path

from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import get_workspace_config_path, initialize_workspace_config

from ._shared import require_workspace_path


@dataclass(frozen=True)
class ConfigInitializeInput:
    pass


@dataclass(frozen=True)
class ConfigInitializeResult:
    path: Path


def run(input_data: ConfigInitializeInput) -> ConfigInitializeResult:
    workspace_path = require_workspace_path()
    if get_workspace_config_path().exists():
        raise WorkspaceError("Workspace config already exists. Use 'wv workspace migrate' or 'wv config set'.")
    config_path = initialize_workspace_config(workspace_path)
    return ConfigInitializeResult(path=config_path)
