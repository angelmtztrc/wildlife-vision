from dataclasses import dataclass
from pathlib import Path

from wv.workspace.workspace_config import get_workspace_config_path, load_workspace_config, validate_workspace_config

from ._shared import require_workspace_path


@dataclass(frozen=True)
class ValidateConfigInput:
    pass


@dataclass(frozen=True)
class ValidateConfigResult:
    path: Path


def run(input_data: ValidateConfigInput) -> ValidateConfigResult:
    workspace_path = require_workspace_path()
    validate_workspace_config(load_workspace_config(), workspace_path)
    return ValidateConfigResult(path=get_workspace_config_path())
