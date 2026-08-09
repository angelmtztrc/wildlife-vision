from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.monitoring_area._shared import MonitoringAreaError
from wv.use_cases.monitoring_area.create import CreateMonitoringAreaInput, run as run_create
from wv.use_cases.monitoring_area.list import ListMonitoringAreasInput, run as run_list
from wv.use_cases.monitoring_area.show import ShowMonitoringAreaInput, run as run_show
from wv.use_cases.monitoring_area.update import UpdateMonitoringAreaInput, run as run_update
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage monitoring areas.")
logger = get_logger(__name__)


@app.command("create")
def create(
    name: Annotated[str, typer.Option(help="Monitoring area name.")],
    area_id: Annotated[
        str | None,
        typer.Option("--id", help="Identifier; defaults to the normalized name."),
    ] = None,
    description: Annotated[str | None, typer.Option(help="Monitoring area description.")] = None,
    notes: Annotated[str | None, typer.Option(help="Monitoring area notes.")] = None,
):
    """Create a monitoring area in the active workspace."""
    try:
        result = run_create(
            CreateMonitoringAreaInput(
                name=name,
                id=area_id,
                description=description,
                notes=notes,
            )
        )
    except (WorkspaceError, MonitoringAreaError) as exc:
        logger.error("Monitoring area creation failed: %s", exc)
        raise typer.Exit(code=1) from exc
    logger.done("Monitoring area created: %s (%s)", result.monitoring_area.id, result.monitoring_area.name)


@app.command("list")
def list_items():
    """List monitoring areas in the active workspace."""
    try:
        result = run_list(ListMonitoringAreasInput())
    except WorkspaceError as exc:
        logger.error("Monitoring area list failed: %s", exc)
        raise typer.Exit(code=1) from exc
    for item in result.items:
        typer.echo(f"{item.id}\t{item.name}")


@app.command("show")
def show(area_id: Annotated[str, typer.Argument(help="Monitoring area ID.")]):
    """Show one monitoring area."""
    try:
        result = run_show(ShowMonitoringAreaInput(area_id))
    except (WorkspaceError, MonitoringAreaError) as exc:
        logger.error("Monitoring area show failed: %s", exc)
        raise typer.Exit(code=1) from exc
    item = result.monitoring_area
    typer.echo(f"id: {item.id}\nname: {item.name}\ndescription: {item.description or ''}\nnotes: {item.notes or ''}")


@app.command("update")
def update(
    area_id: Annotated[str, typer.Argument(help="Monitoring area ID.")],
    name: Annotated[str | None, typer.Option(help="Monitoring area name.")] = None,
    description: Annotated[str | None, typer.Option(help="Monitoring area description.")] = None,
    notes: Annotated[str | None, typer.Option(help="Monitoring area notes.")] = None,
):
    """Update one or more fields on a monitoring area."""
    try:
        result = run_update(UpdateMonitoringAreaInput(area_id, name, description, notes))
    except (WorkspaceError, MonitoringAreaError) as exc:
        logger.error("Monitoring area update failed: %s", exc)
        raise typer.Exit(code=1) from exc
    logger.done("Monitoring area updated: %s (%s)", result.monitoring_area.id, result.monitoring_area.name)
