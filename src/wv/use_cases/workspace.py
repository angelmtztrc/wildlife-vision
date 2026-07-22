import os
from dataclasses import dataclass
from pathlib import Path

from wv.persistence import initialize_database
from wv.workspace.config import get_global_config_file, get_workspace_path, write_global_config
from wv.workspace.common import WORKSPACE_CONFIG_NAME, WORKSPACE_DATABASE_NAME, WORKSPACE_DIRECTORIES, WORKSPACE_METADATA_DIRNAME, WorkspaceError
from wv.workspace.workspace_config import initialize_workspace_config


@dataclass(frozen=True)
class WorkspaceInitInput:
    path: Path


@dataclass(frozen=True)
class WorkspaceInitResult:
    workspace_path: Path
    global_config_file: Path
    metadata_dir: Path
    database_file: Path
    workspace_config_file: Path


@dataclass(frozen=True)
class WorkspaceStatus:
    global_config_file: Path
    workspace_path: Path | None
    exists: bool
    sessions_exists: bool
    models_exists: bool
    exports_exists: bool
    metadata_exists: bool
    database_exists: bool
    workspace_config_exists: bool


def _resolve_workspace_paths(workspace_path: Path) -> dict[str, Path]:
    metadata_dir = workspace_path / WORKSPACE_METADATA_DIRNAME
    return {
        "sessions": workspace_path / "sessions",
        "models": workspace_path / "models",
        "exports": workspace_path / "exports",
        "metadata_dir": metadata_dir,
        "database_file": metadata_dir / WORKSPACE_DATABASE_NAME,
        "workspace_config_file": metadata_dir / WORKSPACE_CONFIG_NAME,
    }


def _validate_workspace_parent(path: Path) -> Path:
    workspace_path = path.expanduser().resolve()

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
def run_init(input_data: WorkspaceInitInput) -> WorkspaceInitResult:
    workspace_path = _validate_workspace_parent(input_data.path)
    paths = _resolve_workspace_paths(workspace_path)

    for directory_name in WORKSPACE_DIRECTORIES:
        paths[directory_name].mkdir(parents=True, exist_ok=True)

    metadata_dir = paths["metadata_dir"]
    metadata_dir.mkdir(parents=True, exist_ok=True)

    database_file = paths["database_file"]
    initialize_database(database_file)

    workspace_config_file = paths["workspace_config_file"]
    initialize_workspace_config(workspace_path, config_file=workspace_config_file)

    global_config_file = write_global_config(
        {
            "workspace": {
                "path": str(workspace_path),
            }
        }
    )

    return WorkspaceInitResult(
        workspace_path=workspace_path,
        global_config_file=global_config_file,
        metadata_dir=metadata_dir,
        database_file=database_file,
        workspace_config_file=workspace_config_file,
    )


def get_status() -> WorkspaceStatus:
    global_config_file = get_global_config_file()
    workspace_path = get_workspace_path()

    if workspace_path is None:
        return WorkspaceStatus(
            global_config_file=global_config_file,
            workspace_path=None,
            exists=False,
            sessions_exists=False,
            models_exists=False,
            exports_exists=False,
            metadata_exists=False,
            database_exists=False,
            workspace_config_exists=False,
        )

    paths = _resolve_workspace_paths(workspace_path)
    return WorkspaceStatus(
        global_config_file=global_config_file,
        workspace_path=workspace_path,
        exists=workspace_path.exists() and workspace_path.is_dir(),
        sessions_exists=paths["sessions"].is_dir(),
        models_exists=paths["models"].is_dir(),
        exports_exists=paths["exports"].is_dir(),
        metadata_exists=paths["metadata_dir"].is_dir(),
        database_exists=paths["database_file"].is_file(),
        workspace_config_exists=paths["workspace_config_file"].is_file(),
    )


def validate() -> WorkspaceStatus:
    status = get_status()

    if status.workspace_path is None:
        raise WorkspaceError("No workspace configured.")

    if not status.exists:
        raise WorkspaceError(f"Workspace path does not exist: {status.workspace_path}")
    if not status.sessions_exists:
        raise WorkspaceError("Missing workspace directory: sessions")
    if not status.models_exists:
        raise WorkspaceError("Missing workspace directory: models")
    if not status.exports_exists:
        raise WorkspaceError("Missing workspace directory: exports")
    if not status.metadata_exists:
        raise WorkspaceError("Missing workspace metadata directory: .wv")
    if not status.database_exists:
        raise WorkspaceError("Missing workspace database file: .wv/database.sqlite")
    if not status.workspace_config_exists:
        raise WorkspaceError("Missing workspace config file: .wv/config.yml")

    return status
