from dataclasses import dataclass

from wv.workspace.common import WorkspaceError

from ._shared import WorkspaceStatus, get_workspace_status, validate_workspace_candidate


@dataclass(frozen=True)
class WorkspaceValidateInput:
    pass


@dataclass(frozen=True)
class WorkspaceValidateResult:
    status: WorkspaceStatus


def run(input_data: WorkspaceValidateInput) -> WorkspaceValidateResult:
    status = get_workspace_status()

    if status.workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    validate_workspace_candidate(
        status.workspace_path, require_current=True, require_writable=False
    )

    return WorkspaceValidateResult(status=status)
