from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.monitoring_site._shared import MonitoringSiteError
from wv.use_cases.monitoring_site.create import (
    CreateMonitoringSiteInput,
    run as run_create_monitoring_site,
)
from wv.use_cases.monitoring_site.list import (
    ListMonitoringSitesInput,
    run as run_list_monitoring_sites,
)
from wv.use_cases.monitoring_site.show import (
    ShowMonitoringSiteInput,
    run as run_show_monitoring_site,
)
from wv.use_cases.monitoring_site.update import (
    UpdateMonitoringSiteInput,
    run as run_update_monitoring_site,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage monitoring sites.")

logger = get_logger(__name__)


def _format_value(value: object) -> str:
    return "" if value is None else str(value)


@app.command("create")
def create(
    site_id: Annotated[str, typer.Argument(help="Monitoring site ID.")],
    area: Annotated[str, typer.Option("--area", help="Parent monitoring area ID.")],
    name: Annotated[str, typer.Option(help="Monitoring site name.")],
    latitude: Annotated[float, typer.Option(help="Monitoring site latitude.")],
    longitude: Annotated[float, typer.Option(help="Monitoring site longitude.")],
    description: Annotated[str | None, typer.Option(help="Monitoring site description.")] = None,
    elevation: Annotated[float | None, typer.Option(help="Monitoring site elevation.")] = None,
    notes: Annotated[str | None, typer.Option(help="Monitoring site notes.")] = None,
):
    try:
        result = run_create_monitoring_site(
            CreateMonitoringSiteInput(
                id=site_id,
                monitoring_area_id=area,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
                notes=notes,
            )
        )
    except (WorkspaceError, MonitoringSiteError) as exc:
        logger.error("Monitoring site creation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "Monitoring site created: %s (%s)",
        result.monitoring_site.id,
        result.monitoring_site.name,
    )
    return None


@app.command("list")
def list_sites(
    area: Annotated[
        str | None, typer.Option("--area", help="Only show sites in this area.")
    ] = None,
):
    try:
        result = run_list_monitoring_sites(ListMonitoringSitesInput(monitoring_area_id=area))
    except WorkspaceError as exc:
        logger.error("Monitoring site list failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for site in result.items:
        typer.echo(f"{site.id}\t{site.monitoring_area_id}\t{site.name}")

    return None


@app.command("show")
def show(site_id: Annotated[str, typer.Argument(help="Monitoring site ID.")]):
    try:
        result = run_show_monitoring_site(ShowMonitoringSiteInput(id=site_id))
    except (WorkspaceError, MonitoringSiteError) as exc:
        logger.error("Monitoring site show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"id: {result.monitoring_site.id}")
    typer.echo(f"area: {result.monitoring_site.monitoring_area_id}")
    typer.echo(f"name: {result.monitoring_site.name}")
    typer.echo(f"description: {_format_value(result.monitoring_site.description)}")
    typer.echo(f"latitude: {_format_value(result.monitoring_site.latitude)}")
    typer.echo(f"longitude: {_format_value(result.monitoring_site.longitude)}")
    typer.echo(f"elevation: {_format_value(result.monitoring_site.elevation)}")
    typer.echo(f"notes: {_format_value(result.monitoring_site.notes)}")
    return None


@app.command("update")
def update(
    site_id: Annotated[str, typer.Argument(help="Monitoring site ID.")],
    name: Annotated[str | None, typer.Option(help="Monitoring site name.")] = None,
    description: Annotated[str | None, typer.Option(help="Monitoring site description.")] = None,
    latitude: Annotated[float | None, typer.Option(help="Monitoring site latitude.")] = None,
    longitude: Annotated[float | None, typer.Option(help="Monitoring site longitude.")] = None,
    elevation: Annotated[float | None, typer.Option(help="Monitoring site elevation.")] = None,
    notes: Annotated[str | None, typer.Option(help="Monitoring site notes.")] = None,
):
    try:
        result = run_update_monitoring_site(
            UpdateMonitoringSiteInput(
                id=site_id,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
                notes=notes,
            )
        )
    except (WorkspaceError, MonitoringSiteError) as exc:
        logger.error("Monitoring site update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "Monitoring site updated: %s (%s)",
        result.monitoring_site.id,
        result.monitoring_site.name,
    )
    return None
