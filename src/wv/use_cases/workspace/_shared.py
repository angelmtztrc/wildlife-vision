import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from wv.core.files import SymlinkPathError, ensure_not_symlink, ensure_tree_has_no_symlinks
from wv.persistence.database import get_database_head_revision, get_database_revision
from wv.workspace.common import (
    WORKSPACE_CONFIG_NAME,
    WORKSPACE_DATABASE_NAME,
    WORKSPACE_METADATA_DIRNAME,
    WorkspaceError,
)
from wv.workspace.config import get_global_config_file, get_workspace_path
from wv.workspace.schema import WORKSPACE_VERSION
from wv.workspace.workspace_config import load_workspace_config, validate_workspace_config


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


@dataclass(frozen=True)
class WorkspaceCandidate:
    workspace_path: Path
    paths: WorkspacePaths
    config_version: int
    database_revision: str
    database_head_revision: str

    @property
    def migration_required(self) -> bool:
        return (
            self.config_version != WORKSPACE_VERSION
            or self.database_revision != self.database_head_revision
        )


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


def validate_workspace_candidate(
    path: Path, *, require_current: bool, require_writable: bool
) -> WorkspaceCandidate:
    requested_path = path.expanduser().absolute()
    try:
        ensure_not_symlink(requested_path)
        workspace_path = requested_path.resolve(strict=True)
        ensure_tree_has_no_symlinks(workspace_path)
    except (FileNotFoundError, NotADirectoryError, OSError, SymlinkPathError) as exc:
        raise WorkspaceError(str(exc)) from exc

    if not os.access(workspace_path, os.R_OK):
        raise WorkspaceError(f"Workspace path is not readable: {workspace_path}")
    if require_writable and not os.access(workspace_path, os.W_OK):
        raise WorkspaceError(f"Workspace path is not writable: {workspace_path}")

    paths = resolve_workspace_paths(workspace_path)
    required_directories = {
        "sessions": paths.sessions,
        "models": paths.models,
        "exports": paths.exports,
        ".wv": paths.metadata_dir,
    }
    for name, directory in required_directories.items():
        if not directory.is_dir():
            raise WorkspaceError(f"Missing workspace directory: {name}")
    if not paths.database_file.is_file():
        raise WorkspaceError("Missing workspace database file: .wv/database.sqlite")
    if not paths.workspace_config_file.is_file():
        raise WorkspaceError("Missing workspace config file: .wv/config.yml")

    config = load_workspace_config(paths.workspace_config_file)
    validate_workspace_config(config, workspace_path)
    config_version = config["workspace"]["version"]

    try:
        database_revision = get_database_revision(paths.database_file)
        database_head_revision = get_database_head_revision()
    except (CommandError, OSError, SQLAlchemyError, sqlite3.DatabaseError) as exc:
        raise WorkspaceError(f"Unable to inspect workspace database: {exc}") from exc
    if database_revision is None:
        raise WorkspaceError(
            "Workspace database has no Alembic revision and cannot be migrated "
            "automatically. Restore a compatible backup or create a new workspace."
        )

    candidate = WorkspaceCandidate(
        workspace_path=workspace_path,
        paths=paths,
        config_version=config_version,
        database_revision=database_revision,
        database_head_revision=database_head_revision,
    )
    if require_current and candidate.config_version != WORKSPACE_VERSION:
        raise WorkspaceError("Workspace config is version 1. Run 'wv workspace migrate'.")
    if require_current and candidate.database_revision != candidate.database_head_revision:
        raise WorkspaceError(
            "Workspace database is not up to date. Run 'wv workspace migrate'."
        )
    return candidate


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
