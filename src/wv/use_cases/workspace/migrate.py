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
    get_workspace_config_path,
    load_workspace_config,
    migrate_workspace_config_v1_to_v2,
    migrate_workspace_config_v2_to_v3,
    require_workspace_database_path,
    require_workspace_path,
    validate_workspace_config,
    write_workspace_config,
)


@dataclass(frozen=True)
class WorkspaceMigrateInput:
    pass


@dataclass(frozen=True)
class WorkspaceMigrateResult:
    workspace_path: Path
    config_path: Path
    database_path: Path
    previous_config_version: int
    current_config_version: int
    config_migrated: bool
    previous_database_revision: str
    current_database_revision: str
    database_migrated: bool

    @property
    def migrated(self) -> bool:
        return self.config_migrated or self.database_migrated


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
    config_path = get_workspace_config_path()
    database_path = require_workspace_database_path(workspace_path)
    config = load_workspace_config(config_path)
    previous_config_version = config.get("workspace", {}).get("version")
    if isinstance(previous_config_version, bool) or not isinstance(previous_config_version, int):
        raise WorkspaceError("Workspace config has an invalid version.")
    if previous_config_version == 1:
        migrated_config = migrate_workspace_config_v1_to_v2(config, workspace_path)
    elif previous_config_version == 2:
        migrated_config = migrate_workspace_config_v2_to_v3(config, workspace_path)
    else:
        validate_workspace_config(config, workspace_path)
        migrated_config = config
    if previous_config_version not in {1, 2, 3}:
        raise WorkspaceError(f"Unsupported workspace config version: {previous_config_version}")
    previous_revision = _get_database_revision(database_path)

    try:
        head_revision = get_database_head_revision()
    except CommandError as exc:
        raise WorkspaceError(f"Unable to resolve packaged database migration head: {exc}") from exc

    database_migrated = previous_revision != head_revision
    if database_migrated:
        try:
            upgrade_database(database_path)
        except (CommandError, OSError, SQLAlchemyError, sqlite3.DatabaseError) as exc:
            raise WorkspaceError(f"Workspace database migration failed: {exc}") from exc
        current_revision = _get_database_revision(database_path)
        if current_revision != head_revision:
            raise WorkspaceError("Workspace database migration did not reach the packaged migration head.")
    else:
        current_revision = previous_revision
    config_migrated = previous_config_version in {1, 2}
    if config_migrated:
        write_workspace_config(migrated_config, config_path)
        validate_workspace_config(load_workspace_config(config_path), workspace_path)

    return WorkspaceMigrateResult(
        workspace_path=workspace_path,
        config_path=config_path,
        database_path=database_path,
        previous_config_version=previous_config_version,
        current_config_version=3,
        config_migrated=config_migrated,
        previous_database_revision=previous_revision,
        current_database_revision=current_revision,
        database_migrated=database_migrated,
    )
