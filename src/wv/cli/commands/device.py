from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.device import (
    DeviceInput,
    DeviceUpdateInput,
    RecordAlreadyExistsError,
    RecordNotFoundError,
    run_create,
    run_list,
    run_show,
    run_update,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage devices.")

logger = get_logger(__name__)


def _format_value(value: object) -> str:
    return "" if value is None else str(value)


@app.command("create")
def create(
    device_id: Annotated[str, typer.Argument(help="Device ID.")],
    name: Annotated[str, typer.Option(help="Device name.")],
    manufacturer: Annotated[str | None, typer.Option(help="Device manufacturer.")] = None,
    serial_number: Annotated[
        str | None, typer.Option("--serial-number", help="Device serial number.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Device notes.")] = None,
):
    try:
        result = run_create(
            DeviceInput(
                id=device_id,
                name=name,
                manufacturer=manufacturer,
                serial_number=serial_number,
                notes=notes,
            )
        )
    except (WorkspaceError, RecordAlreadyExistsError) as exc:
        logger.error("Device creation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Device created: %s (%s)", result.id, result.name)
    return None


@app.command("list")
def list_items():
    try:
        result = run_list()
    except WorkspaceError as exc:
        logger.error("Device list failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for device in result:
        typer.echo(f"{device.id}\t{device.name}")

    return None


@app.command("show")
def show(device_id: Annotated[str, typer.Argument(help="Device ID.")]):
    try:
        result = run_show(device_id)
    except (WorkspaceError, RecordNotFoundError) as exc:
        logger.error("Device show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"id: {result.id}")
    typer.echo(f"name: {result.name}")
    typer.echo(f"manufacturer: {_format_value(result.manufacturer)}")
    typer.echo(f"serial_number: {_format_value(result.serial_number)}")
    typer.echo(f"notes: {_format_value(result.notes)}")
    return None


@app.command("update")
def update(
    device_id: Annotated[str, typer.Argument(help="Device ID.")],
    name: Annotated[str | None, typer.Option(help="Device name.")] = None,
    manufacturer: Annotated[str | None, typer.Option(help="Device manufacturer.")] = None,
    serial_number: Annotated[
        str | None, typer.Option("--serial-number", help="Device serial number.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Device notes.")] = None,
):
    try:
        result = run_update(
            DeviceUpdateInput(
                id=device_id,
                name=name,
                manufacturer=manufacturer,
                serial_number=serial_number,
                notes=notes,
            )
        )
    except (WorkspaceError, RecordNotFoundError) as exc:
        logger.error("Device update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Device updated: %s (%s)", result.id, result.name)
    return None
