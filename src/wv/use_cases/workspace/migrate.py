import sqlite3
from dataclasses import dataclass
from pathlib import Path

from alembic.util.exc import CommandError
from sqlalchemy.exc import SQLAlchemyError

from wv.persistence.database import (
    get_database_head_revision,
    get_database_revision,
    upgrade_database,
)
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import (
    require_workspace_database_path,
    require_workspace_path,
)


@dataclass(frozen=True)
class WorkspaceMigrateInput:
    pass


@dataclass(frozen=True)
class WorkspaceMigrateResult:
    workspace_path: Path
    database_path: Path
    previous_revision: str
    current_revision: str
    migrated: bool


def _get_database_revision(database_path: Path) -> str:
    try:
        revision = get_database_revision(database_path)
    except (CommandError, OSError, SQLAlchemyError, sqlite3.DatabaseError) as exc:
        raise WorkspaceError(f"Unable to inspect workspace database: {exc}") from exc

    if revision is None:
        raise WorkspaceError(
            "Workspace database has no Alembic revision and cannot be migrated safely."
        )

    return revision


def run(input_data: WorkspaceMigrateInput) -> WorkspaceMigrateResult:
    workspace_path = require_workspace_path()
    database_path = require_workspace_database_path(workspace_path)
    previous_revision = _get_database_revision(database_path)

    try:
        head_revision = get_database_head_revision()
    except CommandError as exc:
        raise WorkspaceError(f"Unable to resolve packaged database migration head: {exc}") from exc

    if previous_revision == head_revision:
        return WorkspaceMigrateResult(
            workspace_path=workspace_path,
            database_path=database_path,
            previous_revision=previous_revision,
            current_revision=previous_revision,
            migrated=False,
        )

    try:
        upgrade_database(database_path)
    except (CommandError, OSError, SQLAlchemyError, sqlite3.DatabaseError) as exc:
        raise WorkspaceError(f"Workspace database migration failed: {exc}") from exc

    current_revision = _get_database_revision(database_path)
    if current_revision != head_revision:
        raise WorkspaceError(
            "Workspace database migration did not reach the packaged migration head."
        )

    return WorkspaceMigrateResult(
        workspace_path=workspace_path,
        database_path=database_path,
        previous_revision=previous_revision,
        current_revision=current_revision,
        migrated=True,
    )
