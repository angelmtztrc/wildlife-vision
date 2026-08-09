from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_initialize_workspace,
)
from wv.use_cases.workspace.migrate import WorkspaceMigrateInput, run as run_migrate_workspace
from wv.use_cases.workspace.show import WorkspaceShowInput, run as run_show_workspace
from wv.use_cases.workspace.validate import (
    WorkspaceValidateInput,
    run as run_validate_workspace,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Initialize, inspect, migrate, and validate the active workspace.")

logger = get_logger(__name__)


@app.command("init")
def init_workspace(
    path: Annotated[
        Path,
        typer.Argument(
            help="Existing readable and writable directory to initialize and activate.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
        ),
    ],
):
    """Initialize and activate an existing directory as a workspace."""
    logger.info("Initializing workspace at %s", display_path(path))

    try:
        result = run_initialize_workspace(WorkspaceInitializeInput(path=path))
    except WorkspaceError as exc:
        logger.error("Workspace initialization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "Workspace initialized at %s (global_config=%s, database=%s)",
        display_path(result.workspace_path),
        display_path(result.global_config_file),
        display_path(result.database_file),
    )

    return None


@app.command("migrate")
def migrate_workspace():
    """Upgrade the active workspace config and database to current versions."""
    try:
        result = run_migrate_workspace(WorkspaceMigrateInput())
    except WorkspaceError as exc:
        logger.error("Workspace migration failed: %s", exc)
        raise typer.Exit(code=1) from exc

    if result.migrated:
        logger.done(
            "Workspace migrated at %s (config=%s -> %s, database=%s -> %s)",
            display_path(result.workspace_path),
            result.previous_config_version,
            result.current_config_version,
            result.previous_database_revision,
            result.current_database_revision,
        )
    else:
        logger.done(
            "Workspace is already up to date at %s (config=%s, database=%s)",
            display_path(result.workspace_path),
            result.current_config_version,
            result.current_database_revision,
        )

    return None


@app.command("show")
def show_workspace():
    """Show the configured workspace path and required component status."""
    status = run_show_workspace(WorkspaceShowInput()).status

    typer.echo(f"global_config: {status.global_config_file}")
    typer.echo(
        "workspace_path: "
        f"{status.workspace_path if status.workspace_path is not None else 'not configured'}"
    )

    if status.workspace_path is None:
        return None

    typer.echo(f"exists: {status.exists}")
    typer.echo(f"sessions: {status.sessions_exists}")
    typer.echo(f"models: {status.models_exists}")
    typer.echo(f"exports: {status.exports_exists}")
    typer.echo(f"metadata: {status.metadata_exists}")
    typer.echo(f"database: {status.database_exists}")
    typer.echo(f"workspace_config: {status.workspace_config_exists}")

    return None


@app.command("validate")
def validate_workspace_command():
    """Validate the active workspace structure, config, and database revision."""
    try:
        status = run_validate_workspace(WorkspaceValidateInput()).status
    except WorkspaceError as exc:
        logger.error("Workspace validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace is valid at %s", display_path(status.workspace_path))
    return None
