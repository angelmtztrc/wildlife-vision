import os
from dataclasses import dataclass
from pathlib import Path

from wv.core.files import SymlinkPathError, ensure_not_symlink
from wv.persistence import initialize_database
from wv.workspace.common import WORKSPACE_DIRECTORIES, WORKSPACE_METADATA_DIRNAME, WorkspaceError
from wv.workspace.config import write_global_config
from wv.workspace.workspace_config import initialize_workspace_config

from ._shared import resolve_workspace_paths


@dataclass(frozen=True)
class WorkspaceInitializeInput:
    path: Path


@dataclass(frozen=True)
class WorkspaceInitializeResult:
    workspace_path: Path
    global_config_file: Path
    metadata_dir: Path
    database_file: Path
    workspace_config_file: Path


def _validate_workspace_parent(path: Path) -> Path:
    workspace_path = path.expanduser().absolute()

    try:
        ensure_not_symlink(workspace_path)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not workspace_path.exists():
        raise WorkspaceError(f"Workspace path does not exist: {workspace_path}")
    if not workspace_path.is_dir():
        raise WorkspaceError(f"Workspace path is not a directory: {workspace_path}")
    if not os.access(workspace_path, os.R_OK):
        raise WorkspaceError(f"Workspace path is not readable: {workspace_path}")
    if not os.access(workspace_path, os.W_OK):
        raise WorkspaceError(f"Workspace path is not writable: {workspace_path}")

    metadata_dir = workspace_path / WORKSPACE_METADATA_DIRNAME
    if metadata_dir.exists():
        raise WorkspaceError(f"Workspace already exists at: {workspace_path}")

    return workspace_path


def run(input_data: WorkspaceInitializeInput) -> WorkspaceInitializeResult:
    workspace_path = _validate_workspace_parent(input_data.path)
    paths = resolve_workspace_paths(workspace_path)

    for directory_name in WORKSPACE_DIRECTORIES:
        getattr(paths, directory_name).mkdir(parents=True, exist_ok=True)

    paths.metadata_dir.mkdir(parents=True, exist_ok=True)
    initialize_database(paths.database_file)
    initialize_workspace_config(workspace_path, config_file=paths.workspace_config_file)

    global_config_file = write_global_config(
        {
            "workspace": {
                "path": str(workspace_path),
            }
        }
    )

    return WorkspaceInitializeResult(
        workspace_path=workspace_path,
        global_config_file=global_config_file,
        metadata_dir=paths.metadata_dir,
        database_file=paths.database_file,
        workspace_config_file=paths.workspace_config_file,
    )
