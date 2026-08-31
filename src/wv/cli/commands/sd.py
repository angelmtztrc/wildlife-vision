from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.sd._shared import SdError
from wv.use_cases.sd.clear import SdClearInput, run as run_clear
from wv.use_cases.sd.initialize import SdInitializeInput, run as run_initialize
from wv.use_cases.sd.show import SdShowInput, run as run_show
from wv.use_cases.sd.update import SdUpdateInput, run as run_update
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage monitoring-site metadata stored on SD cards.")

logger = get_logger(__name__)


@app.command("init")
def init_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD-card directory to initialize.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
        ),
    ],
    monitoring_site: Annotated[
        str,
        typer.Option("--monitoring-site", help="Registered monitoring-site ID from the active workspace."),
    ],
):
    """Write monitoring-site metadata to an uninitialized SD card."""
    try:
        result = run_initialize(
            SdInitializeInput(
                path=path,
                monitoring_site_id=monitoring_site,
            )
        )
    except (WorkspaceError, SdError) as exc:
        logger.error("SD initialization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD initialized at %s (monitoring_site=%s)",
        display_path(result.path),
        result.config.monitoring_site_id,
    )
    return None


@app.command("show")
def show_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD-card directory to inspect.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
):
    """Show monitoring-site metadata stored on an initialized SD card."""
    try:
        result = run_show(SdShowInput(path=path))
    except SdError as exc:
        logger.error("SD show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"path: {result.path}")
    typer.echo(f"config_path: {result.config_path}")
    typer.echo(f"monitoring_site_id: {result.config.monitoring_site_id}")
    typer.echo(f"created_at: {result.config.created_at}")
    typer.echo(f"updated_at: {result.config.updated_at}")
    return None


@app.command("update")
def update_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD-card directory to update.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
        ),
    ],
    monitoring_site: Annotated[
        str,
        typer.Option("--monitoring-site", help="Registered monitoring-site ID from the active workspace."),
    ],
):
    """Change the monitoring site stored on an initialized SD card."""
    try:
        result = run_update(
            SdUpdateInput(
                path=path,
                monitoring_site_id=monitoring_site,
            )
        )
    except (WorkspaceError, SdError) as exc:
        logger.error("SD update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD updated at %s (monitoring_site=%s)",
        display_path(result.path),
        result.config.monitoring_site_id,
    )
    return None


@app.command("clear")
def clear_sd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Mounted SD-card directory whose .wv/config.yml file will be removed.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
        ),
    ],
):
    """Remove the SD card's Wildlife Vision config file without deleting images."""
    try:
        result = run_clear(SdClearInput(path=path))
    except (WorkspaceError, SdError) as exc:
        logger.error("SD clear failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "SD cleared at %s",
        display_path(result.path),
    )
    return None
