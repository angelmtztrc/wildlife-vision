from dataclasses import dataclass

from ._shared import WorkspaceStatus, get_workspace_status


@dataclass(frozen=True)
class WorkspaceShowInput:
    pass


@dataclass(frozen=True)
class WorkspaceShowResult:
    status: WorkspaceStatus


def run(input_data: WorkspaceShowInput) -> WorkspaceShowResult:
    return WorkspaceShowResult(status=get_workspace_status())
