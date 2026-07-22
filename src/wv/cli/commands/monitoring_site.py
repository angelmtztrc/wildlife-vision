from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.monitoring_site import (
    MonitoringSiteInput,
    MonitoringSiteUpdateInput,
    RecordAlreadyExistsError,
    RecordNotFoundError,
    run_create,
    run_list,
    run_show,
    run_update,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage monitoring sites.")

logger = get_logger(__name__)


def _format_value(value: object) -> str:
    return "" if value is None else str(value)


@app.command("create")
def create(
    site_id: Annotated[str, typer.Argument(help="Monitoring site ID.")],
    name: Annotated[str, typer.Option(help="Monitoring site name.")],
    description: Annotated[str | None, typer.Option(help="Monitoring site description.")] = None,
    latitude: Annotated[float | None, typer.Option(help="Monitoring site latitude.")] = None,
    longitude: Annotated[float | None, typer.Option(help="Monitoring site longitude.")] = None,
    elevation: Annotated[float | None, typer.Option(help="Monitoring site elevation.")] = None,
    notes: Annotated[str | None, typer.Option(help="Monitoring site notes.")] = None,
):
    try:
        result = run_create(
            MonitoringSiteInput(
                id=site_id,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
                notes=notes,
            )
        )
    except (WorkspaceError, RecordAlreadyExistsError) as exc:
        logger.error("Monitoring site creation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Monitoring site created: %s (%s)", result.id, result.name)
    return None


@app.command("list")
def list_sites():
    try:
        result = run_list()
    except WorkspaceError as exc:
        logger.error("Monitoring site list failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for site in result:
        typer.echo(f"{site.id}\t{site.name}")

    return None


@app.command("show")
def show(site_id: Annotated[str, typer.Argument(help="Monitoring site ID.")]):
    try:
        result = run_show(site_id)
    except (WorkspaceError, RecordNotFoundError) as exc:
        logger.error("Monitoring site show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"id: {result.id}")
    typer.echo(f"name: {result.name}")
    typer.echo(f"description: {_format_value(result.description)}")
    typer.echo(f"latitude: {_format_value(result.latitude)}")
    typer.echo(f"longitude: {_format_value(result.longitude)}")
    typer.echo(f"elevation: {_format_value(result.elevation)}")
    typer.echo(f"notes: {_format_value(result.notes)}")
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
        result = run_update(
            MonitoringSiteUpdateInput(
                id=site_id,
                name=name,
                description=description,
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
                notes=notes,
            )
        )
    except (WorkspaceError, RecordNotFoundError) as exc:
        logger.error("Monitoring site update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Monitoring site updated: %s (%s)", result.id, result.name)
    return None
