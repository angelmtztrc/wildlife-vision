from pathlib import Path
from typing import Annotated, Literal

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
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

app = typer.Typer(help="Create managed sessions from SD cards or folders.")

logger = get_logger(__name__)


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
            help="Mounted SD-card directory containing .wv/config.yml monitoring-site metadata.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    mode: Annotated[
        Literal["drain", "copy"],
        typer.Option(
            help="Ingestion mode: drain copies and verifies each JPEG before deleting its source; copy retains sources.",
        ),
    ] = "drain",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview counts and destinations without creating a session, copying files, or deleting sources.",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            help="Include files in nested directories, excluding .wv metadata directories.",
        ),
    ] = False,
):
    """Ingest JPEGs from an initialized SD card into the active workspace."""
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
            help="Directory containing .jpg and .jpeg files to ingest.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    monitoring_site: Annotated[
        str,
        typer.Option(
            "--monitoring-site",
            help="Registered monitoring-site ID for the new session.",
            autocompletion=_complete_monitoring_site,
        ),
    ],
    mode: Annotated[
        Literal["drain", "copy"],
        typer.Option(
            help="Ingestion mode: drain copies and verifies each JPEG before deleting its source; copy retains sources.",
        ),
    ] = "drain",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview counts and destinations without creating a session, copying files, or deleting sources.",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            help="Include files in nested directories, excluding .wv metadata directories.",
        ),
    ] = False,
):
    """Ingest JPEGs from a folder into a managed session in the active workspace."""
    logger.info(
        "Starting folder ingest from %s (monitoring_site=%s, mode=%s, dry_run=%s, recursive=%s)",
        display_path(source),
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
