from dataclasses import dataclass
from pathlib import Path

from wv.workspace.common import (
    WORKSPACE_CONFIG_NAME,
    WORKSPACE_DATABASE_NAME,
    WORKSPACE_METADATA_DIRNAME,
)
from wv.workspace.config import get_global_config_file, get_workspace_path


@dataclass(frozen=True)
class WorkspacePaths:
    sessions: Path
    models: Path
    exports: Path
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


def resolve_workspace_paths(workspace_path: Path) -> WorkspacePaths:
    metadata_dir = workspace_path / WORKSPACE_METADATA_DIRNAME
    return WorkspacePaths(
        sessions=workspace_path / "sessions",
        models=workspace_path / "models",
        exports=workspace_path / "exports",
        metadata_dir=metadata_dir,
        database_file=metadata_dir / WORKSPACE_DATABASE_NAME,
        workspace_config_file=metadata_dir / WORKSPACE_CONFIG_NAME,
    )


def get_workspace_status() -> WorkspaceStatus:
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

    paths = resolve_workspace_paths(workspace_path)
    return WorkspaceStatus(
        global_config_file=global_config_file,
        workspace_path=workspace_path,
        exists=workspace_path.exists() and workspace_path.is_dir(),
        sessions_exists=paths.sessions.is_dir(),
        models_exists=paths.models.is_dir(),
        exports_exists=paths.exports.is_dir(),
        metadata_exists=paths.metadata_dir.is_dir(),
        database_exists=paths.database_file.is_file(),
        workspace_config_exists=paths.workspace_config_file.is_file(),
    )
