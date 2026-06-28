from pathlib import Path
from typing import Annotated

import typer

from wv.use_cases.clean.corrupted import CleanCorruptedInput
from wv.use_cases.clean.corrupted import run as run_clean_corrupted
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrInput
from wv.use_cases.clean.overexposed_ir import run as run_clean_overexposed_ir

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
def clean_overexposed_ir(
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
    mean_threshold: Annotated[float, typer.Option("--mean-threshold")] = 200.0,
    std_threshold: Annotated[float, typer.Option("--std-threshold")] = 25.0,
    high_level: Annotated[int, typer.Option("--high-level")] = 220,
    ptc_high_threshold: Annotated[float, typer.Option("--ptc-high-threshold")] = 0.60,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    result = run_clean_overexposed_ir(
        CleanOverexposedIrInput(
            source=source,
            output=output,
            mean_threshold=mean_threshold,
            std_threshold=std_threshold,
            high_level=high_level,
            ptc_high_threshold=ptc_high_threshold,
            dry_run=dry_run,
        )
    )

    typer.echo(f"Source: {source}")
    typer.echo(f"Destination: {result.destination}")
    typer.echo(f"Dry run: {'yes' if result.dry_run else 'no'}")
    typer.echo(f"Discovered: {result.files_discovered}")
    typer.echo(f"Overexposed: {result.files_overexposed}")
    typer.echo(f"Moved: {result.files_moved}")
    typer.echo(f"Ignored: {result.files_ignored}")
    typer.echo(f"Failed: {result.files_failed}")

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("bursts")
def clean_bursts():
    return None
