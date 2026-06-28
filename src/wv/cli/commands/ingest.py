from pathlib import Path
from typing import Annotated, Literal

import typer

from wv.cli.presentation import render_command_summary
from wv.cli.runtime import get_logger, get_runtime
from wv.config import get_device_ids, get_monitoring_sites_ids
from wv.use_cases.ingest.sd import IngestSdInput, run as run_ingest_sd

app = typer.Typer(help="Ingest photos from SD cards and other source locations.")


def _complete_device(incomplete: str) -> list[str]:
    return [device_id for device_id in get_device_ids() if device_id.startswith(incomplete)]


def _complete_monitoring_site(incomplete: str) -> list[str]:
    return [site_id for site_id in get_monitoring_sites_ids() if site_id.startswith(incomplete)]


def _validate_device(value: str) -> str:
    if value not in get_device_ids():
        raise typer.BadParameter(f"Unknown device '{value}'.")
    return value


def _validate_monitoring_site(value: str) -> str:
    if value not in get_monitoring_sites_ids():
        raise typer.BadParameter(f"Unknown monitoring site '{value}'.")
    return value


@app.command("sd")
def ingest_sd(
    source: Annotated[
        Path,
        typer.Argument(help="", exists=True, file_okay=False, dir_okay=True, readable=True),
    ],
    device: Annotated[
        str,
        typer.Option(help="", autocompletion=_complete_device, callback=_validate_device),
    ],
    monitoring_site: Annotated[
        str,
        typer.Option(
            help="",
            autocompletion=_complete_monitoring_site,
            callback=_validate_monitoring_site,
        ),
    ],
    mode: Annotated[
        Literal["drain", "copy"],
        typer.Option(
            help="Ingestion mode. Use 'drain' to safely copy files and remove them from the source location, or 'copy' to copy files while leaving the source unchanged.",
        ),
    ] = "drain",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the ingest operation without copying, moving, or deleting files.",
        ),
    ] = False,
):
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting ingest.sd. Source: %s. Device: %s. Monitoring site: %s. Mode: %s. Dry run: %s.",
        source,
        device,
        monitoring_site,
        mode,
        "yes" if dry_run else "no",
    )

    result = run_ingest_sd(
        IngestSdInput(
            source=source,
            device=device,
            monitoring_site=monitoring_site,
            mode=mode,
            dry_run=dry_run,
        )
    )

    render_command_summary(
        runtime,
        title="Ingest SD Summary",
        message=(
            "Ingest finished."
            if result.files_failed == 0
            else "Ingest finished with failures."
        ),
        rows=[
            ("Source", source),
            ("Destination", result.destination),
            ("Mode", mode),
            ("Dry run", "yes" if result.dry_run else "no"),
            ("Discovered", result.files_discovered),
            ("Copied", result.files_copied),
            ("Replaced", result.files_replaced),
            ("Deleted", result.files_deleted),
            ("Ignored", result.files_ignored),
            ("Failed", result.files_failed),
        ],
        level_name="OK" if result.files_failed == 0 else "ERROR",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("folder")
def ingest_folder(
    source: Annotated[str, typer.Argument(help="")],
    monitoring_site: Annotated[str, typer.Option(help="")],
    mode: Annotated[
        str,
        typer.Option(
            help="Ingestion mode. Use 'drain' to safely copy files and remove them from the source location, or 'copy' to copy files while leaving the source unchanged.",
            autocompletion=lambda: ["drain", "copy"],
        ),
    ] = "drain",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the ingest operation without copying, moving, or deleting files.",
        ),
    ] = False,
):
    return None
