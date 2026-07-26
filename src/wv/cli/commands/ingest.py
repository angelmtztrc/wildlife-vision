from pathlib import Path
from typing import Annotated, Literal

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.device.list import ListDevicesInput, run as run_list_devices
from wv.use_cases.ingest.ingest import (
    ExplicitIngestIdentity,
    IngestInput,
    IngestResult,
    SdCardIngestIdentity,
    run as run_ingest,
)
from wv.use_cases.ingest._shared import IngestError
from wv.use_cases.monitoring_site.list import (
    ListMonitoringSitesInput,
    run as run_list_monitoring_sites,
)
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Ingest photos from SD cards and other source locations.")

logger = get_logger(__name__)


def _complete_device(incomplete: str) -> list[str]:
    try:
        return [
            device.id
            for device in run_list_devices(ListDevicesInput()).items
            if device.id.startswith(incomplete)
        ]
    except WorkspaceError:
        return []


def _complete_monitoring_site(incomplete: str) -> list[str]:
    try:
        return [
            site.id
            for site in run_list_monitoring_sites(ListMonitoringSitesInput()).items
            if site.id.startswith(incomplete)
        ]
    except WorkspaceError:
        return []


def _log_result(source_kind: str, destination: Path, result: IngestResult) -> None:
    logger.done(
        "Finished %s ingest to %s: discovered=%s copied=%s replaced=%s ignored=%s deleted=%s failed=%s%s",
        source_kind,
        display_path(destination),
        result.files_discovered,
        result.files_copied,
        result.files_replaced,
        result.files_ignored,
        result.files_deleted,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )


@app.command("sd")
def ingest_sd(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory representing the mounted SD card to ingest from.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
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
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            help="Scan all nested folders under the source path, excluding .wv directories.",
        ),
    ] = False,
):
    logger.info(
        "Starting SD ingest from %s (mode=%s, dry_run=%s, recursive=%s)",
        display_path(source),
        mode,
        dry_run,
        recursive,
    )

    try:
        result = run_ingest(
            IngestInput(
                source=source,
                mode=mode,
                identity=SdCardIngestIdentity(),
                dry_run=dry_run,
                recursive=recursive,
            )
        )
    except (WorkspaceError, IngestError, ValueError) as exc:
        logger.error("SD ingest failed: %s", exc)
        raise typer.Exit(code=1) from exc

    _log_result("SD", result.destination, result)
    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("folder")
def ingest_folder(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory containing photos to ingest.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    device: Annotated[
        str,
        typer.Option(help="Registered device ID.", autocompletion=_complete_device),
    ],
    monitoring_site: Annotated[
        str,
        typer.Option(
            "--monitoring-site",
            help="Registered monitoring site ID.",
            autocompletion=_complete_monitoring_site,
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
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            help="Scan all nested folders under the source path, excluding .wv directories.",
        ),
    ] = False,
):
    logger.info(
        "Starting folder ingest from %s (device=%s, monitoring_site=%s, mode=%s, dry_run=%s, recursive=%s)",
        display_path(source),
        device,
        monitoring_site,
        mode,
        dry_run,
        recursive,
    )

    try:
        result = run_ingest(
            IngestInput(
                source=source,
                mode=mode,
                identity=ExplicitIngestIdentity(
                    device_id=device,
                    monitoring_site_id=monitoring_site,
                ),
                dry_run=dry_run,
                recursive=recursive,
            )
        )
    except (WorkspaceError, IngestError, ValueError) as exc:
        logger.error("Folder ingest failed: %s", exc)
        raise typer.Exit(code=1) from exc

    _log_result("folder", result.destination, result)
    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
