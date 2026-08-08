from dataclasses import dataclass

from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from wv.core.files import SymlinkPathError, ensure_tree_has_no_symlinks
from wv.persistence.database import get_database_head_revision, get_database_revision
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import load_workspace_config, validate_workspace_config

from ._shared import WorkspaceStatus, get_workspace_status


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

    if not status.exists:
        raise WorkspaceError(f"Workspace path does not exist: {status.workspace_path}")
    try:
        ensure_tree_has_no_symlinks(status.workspace_path)
    except (FileNotFoundError, NotADirectoryError, SymlinkPathError) as exc:
        raise WorkspaceError(str(exc)) from exc
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
    config = load_workspace_config(status.workspace_path / ".wv" / "config.yml")
    validate_workspace_config(config, status.workspace_path)
    if config["workspace"]["version"] != 2:
        raise WorkspaceError("Workspace config is version 1. Run 'wv workspace migrate'.")

    database_path = status.workspace_path / ".wv" / "database.sqlite"
    try:
        current_revision = get_database_revision(database_path)
        head_revision = get_database_head_revision()
    except (CommandError, OSError, SQLAlchemyError) as exc:
        raise WorkspaceError(f"Unable to inspect workspace database: {exc}") from exc

    if current_revision is None:
        raise WorkspaceError(
            "Workspace database has no Alembic revision and cannot be migrated "
            "automatically. Restore a compatible backup or create a new workspace."
        )

    if current_revision != head_revision:
        raise WorkspaceError(
            "Workspace database is not up to date. Run 'wv workspace migrate'."
        )

    return WorkspaceValidateResult(status=status)
