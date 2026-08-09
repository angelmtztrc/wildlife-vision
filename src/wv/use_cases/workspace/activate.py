from dataclasses import dataclass
from pathlib import Path

from wv.workspace.config import get_global_config_file, get_workspace_path, set_workspace_path

from ._shared import validate_workspace_candidate


@dataclass(frozen=True)
class WorkspaceActivateInput:
    path: Path


@dataclass(frozen=True)
class WorkspaceActivateResult:
    workspace_path: Path
    global_config_file: Path
    changed: bool
    migration_required: bool


def run(input_data: WorkspaceActivateInput) -> WorkspaceActivateResult:
    candidate = validate_workspace_candidate(
        input_data.path, require_current=False, require_writable=True
    )
    active_workspace_path = get_workspace_path()
    changed = active_workspace_path != candidate.workspace_path
    global_config_file = (
        set_workspace_path(candidate.workspace_path)
        if changed
        else get_global_config_file()
    )
    return WorkspaceActivateResult(
        workspace_path=candidate.workspace_path,
        global_config_file=global_config_file,
        changed=changed,
        migration_required=candidate.migration_required,
    )
