from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.device._shared import DeviceError
from wv.use_cases.device.create import CreateDeviceInput, run as run_create_device
from wv.use_cases.device.list import ListDevicesInput, run as run_list_devices
from wv.use_cases.device.show import ShowDeviceInput, run as run_show_device
from wv.use_cases.device.update import UpdateDeviceInput, run as run_update_device
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Manage optional device catalog records.")

logger = get_logger(__name__)


def _format_value(value: object) -> str:
    return "" if value is None else str(value)


@app.command("create")
def create(
    device_id: Annotated[str, typer.Argument(help="Unique device ID.")],
    name: Annotated[str, typer.Option(help="Device name.")],
    manufacturer: Annotated[str | None, typer.Option(help="Device manufacturer.")] = None,
    serial_number: Annotated[
        str | None, typer.Option("--serial-number", help="Device serial number.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Device notes.")] = None,
):
    """Create a device record in the active workspace."""
    try:
        result = run_create_device(
            CreateDeviceInput(
                id=device_id,
                name=name,
                manufacturer=manufacturer,
                serial_number=serial_number,
                notes=notes,
            )
        )
    except (WorkspaceError, DeviceError) as exc:
        logger.error("Device creation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Device created: %s (%s)", result.device.id, result.device.name)
    return None


@app.command("list")
def list_items():
    """List device records in the active workspace."""
    try:
        result = run_list_devices(ListDevicesInput())
    except WorkspaceError as exc:
        logger.error("Device list failed: %s", exc)
        raise typer.Exit(code=1) from exc

    for device in result.items:
        typer.echo(f"{device.id}\t{device.name}")

    return None


@app.command("show")
def show(device_id: Annotated[str, typer.Argument(help="Unique device ID.")]):
    """Show one device record."""
    try:
        result = run_show_device(ShowDeviceInput(id=device_id))
    except (WorkspaceError, DeviceError) as exc:
        logger.error("Device show failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"id: {result.device.id}")
    typer.echo(f"name: {result.device.name}")
    typer.echo(f"manufacturer: {_format_value(result.device.manufacturer)}")
    typer.echo(f"serial_number: {_format_value(result.device.serial_number)}")
    typer.echo(f"notes: {_format_value(result.device.notes)}")
    return None


@app.command("update")
def update(
    device_id: Annotated[str, typer.Argument(help="Unique device ID.")],
    name: Annotated[str | None, typer.Option(help="Device name.")] = None,
    manufacturer: Annotated[str | None, typer.Option(help="Device manufacturer.")] = None,
    serial_number: Annotated[
        str | None, typer.Option("--serial-number", help="Device serial number.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="Device notes.")] = None,
):
    """Update one or more fields on a device record."""
    try:
        result = run_update_device(
            UpdateDeviceInput(
                id=device_id,
                name=name,
                manufacturer=manufacturer,
                serial_number=serial_number,
                notes=notes,
            )
        )
    except (WorkspaceError, DeviceError) as exc:
        logger.error("Device update failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Device updated: %s (%s)", result.device.id, result.device.name)
    return None
