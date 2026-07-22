from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.workspace import WorkspaceError, WorkspaceInitInput
from wv.use_cases.workspace import get_status as get_workspace_status
from wv.use_cases.workspace import run_init, validate as validate_workspace

app = typer.Typer(help="Manage workspace initialization and validation.")

logger = get_logger(__name__)


@app.command("init")
def init_workspace(
    path: Annotated[
        Path,
        typer.Argument(
            help="Existing directory to initialize as a workspace.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
        ),
    ],
):
    logger.info("Initializing workspace at %s", display_path(path))

    try:
        result = run_init(WorkspaceInitInput(path=path))
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


@app.command("show")
def show_workspace():
    status = get_workspace_status()

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
    try:
        status = validate_workspace()
    except WorkspaceError as exc:
        logger.error("Workspace validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace is valid at %s", display_path(status.workspace_path))
    return None
