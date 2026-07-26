from dataclasses import dataclass
from pathlib import Path

from wv.workspace.workspace_config import get_workspace_config_path


@dataclass(frozen=True)
class ShowConfigPathInput:
    pass


@dataclass(frozen=True)
class ShowConfigPathResult:
    path: Path


def run(input_data: ShowConfigPathInput) -> ShowConfigPathResult:
    return ShowConfigPathResult(path=get_workspace_config_path())
