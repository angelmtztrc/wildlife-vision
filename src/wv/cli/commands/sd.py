from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.sd import (
    RecordNotFoundError,
    SdClearInput,
    SdError,
    SdInitInput,
    SdSyncInput,
    SdUpdateInput,
    run_clear,
    run_init,
    run_show,
    run_sync,
    run_update,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage SD card metadata and deployment assignment.")

logger = get_logger(__name__)


@app.command("init")
def init_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD card path to initialize.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
        ),
    ],
    device: Annotated[str, typer.Option("--device", help="Registered device ID.")],
    monitoring_site: Annotated[
        str,
        typer.Option("--monitoring-site", help="Registered monitoring site ID."),
    ],
):
    try:
        result = run_init(
            SdInitInput(
                path=path,
                device_id=device,
                monitoring_site_id=monitoring_site,
            )
        )
    except (WorkspaceError, RecordNotFoundError, SdError) as exc:
        logger.error("SD initialization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD initialized at %s (device=%s, monitoring_site=%s)",
        display_path(result.path),
        result.config.device_id,
        result.config.monitoring_site_id,
    )
    return None


@app.command("show")
def show_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD card path to inspect.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ],
):
    try:
        result = run_show(path)
    except SdError as exc:
        logger.error("SD show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"path: {result.path}")
    typer.echo(f"config_path: {result.config_path}")
    typer.echo(f"device_id: {result.config.device_id}")
    typer.echo(f"monitoring_site_id: {result.config.monitoring_site_id}")
    typer.echo(f"created_at: {result.config.created_at}")
    typer.echo(f"updated_at: {result.config.updated_at}")
    return None


@app.command("sync")
def sync_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD card path whose config should synchronize the workspace database.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
        ),
    ],
):
    try:
        result = run_sync(SdSyncInput(path=path))
    except (WorkspaceError, RecordNotFoundError, SdError) as exc:
        logger.error("SD synchronization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    if result.database_updated:
        logger.done(
            "Synchronized workspace database from SD config at %s (device=%s, monitoring_site=%s)",
            display_path(result.path),
            result.config.device_id,
            result.config.monitoring_site_id,
        )
    else:
        logger.done(
            "Workspace database already matches SD config at %s",
            display_path(result.path),
        )
    return None


@app.command("update")
def update_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD card path to update.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
        ),
    ],
    device: Annotated[str | None, typer.Option("--device", help="Registered device ID.")] = None,
    monitoring_site: Annotated[
        str | None,
        typer.Option("--monitoring-site", help="Registered monitoring site ID."),
    ] = None,
):
    try:
        result = run_update(
            SdUpdateInput(
                path=path,
                device_id=device,
                monitoring_site_id=monitoring_site,
            )
        )
    except (WorkspaceError, RecordNotFoundError, SdError) as exc:
        logger.error("SD update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD updated at %s (device=%s, monitoring_site=%s)",
        display_path(result.path),
        result.config.device_id,
        result.config.monitoring_site_id,
    )
    return None


@app.command("clear")
def clear_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD card path to clear.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
        ),
    ],
):
    try:
        result = run_clear(SdClearInput(path=path))
    except (WorkspaceError, RecordNotFoundError, SdError) as exc:
        logger.error("SD clear failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD cleared at %s (device=%s)",
        display_path(result.path),
        result.cleared_device_id,
    )
    return None
