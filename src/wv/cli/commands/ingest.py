from typing import Annotated

import typer

app = typer.Typer(help="Ingest photos from SD cards and other source locations.")


@app.command("sd")
def ingest_sd(
    source: Annotated[str, typer.Argument(help="")],
    device: Annotated[str, typer.Option(help="")],
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
