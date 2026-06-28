from pathlib import Path
from typing import Annotated

import typer

from wv.use_cases.clean.corrupted import CleanCorruptedInput
from wv.use_cases.clean.corrupted import run as run_clean_corrupted

app = typer.Typer(
    help="Identify and clean corrupted, overexposed IR, and burst photos."
)


@app.command("corrupted")
def clean_corrupted(
    source: Annotated[
        Path,
        typer.Argument(
            help="", exists=True, file_okay=False, dir_okay=True, readable=True
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            help="",
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    result = run_clean_corrupted(
        CleanCorruptedInput(source=source, output=output, dry_run=dry_run)
    )

    typer.echo(f"Source: {source}")
    typer.echo(f"Destination: {result.destination}")
    typer.echo(f"Dry run: {'yes' if result.dry_run else 'no'}")
    typer.echo(f"Discovered: {result.files_discovered}")
    typer.echo(f"Corrupted: {result.files_corrupted}")
    typer.echo(f"Moved: {result.files_moved}")
    typer.echo(f"Ignored: {result.files_ignored}")
    typer.echo(f"Failed: {result.files_failed}")

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("overexposed-ir")
def clean_overexposed_ir():
    return None


@app.command("bursts")
def clean_bursts():
    return None
