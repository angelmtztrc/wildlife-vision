from pathlib import Path
from typing import Annotated

import typer

from wv.use_cases.detect.content import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL,
    DetectContentInput,
)
from wv.use_cases.detect.content import run as run_detect_content

app = typer.Typer(help="Run content detection on photos.")


@app.command("content")
def detect_content(
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
        ),
    ],
    model: Annotated[
        str,
        typer.Option(help="MegaDetector model name or path."),
    ] = DEFAULT_MODEL,
    confidence_threshold: Annotated[
        float,
        typer.Option(
            "--confidence-threshold",
            min=0.0,
            max=1.0,
            help="Minimum confidence required to route an image to animal, human, or vehicle; weaker or ambiguous detections go to other.",
        ),
    ] = DEFAULT_CONFIDENCE_THRESHOLD,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            min=1,
            help="Number of images to send to the detector per inference batch.",
        ),
    ] = 32,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the detection operation without moving files or writing metadata.",
        ),
    ] = False,
):
    result = run_detect_content(
        DetectContentInput(
            source=source,
            output=output,
            model=model,
            confidence_threshold=confidence_threshold,
            batch_size=batch_size,
            dry_run=dry_run,
        )
    )

    typer.echo(f"Source: {source}")
    typer.echo(f"Destination: {result.destination}")
    typer.echo(f"Model: {model}")
    typer.echo(f"Confidence threshold: {confidence_threshold}")
    typer.echo(f"Batch size: {batch_size}")
    typer.echo(f"Dry run: {'yes' if result.dry_run else 'no'}")
    typer.echo(f"Discovered: {result.files_discovered}")
    typer.echo(f"Evaluated: {result.files_evaluated}")
    typer.echo(f"Animal: {result.files_animal}")
    typer.echo(f"Human: {result.files_human}")
    typer.echo(f"Vehicle: {result.files_vehicle}")
    typer.echo(f"Empty: {result.files_empty}")
    typer.echo(f"Other: {result.files_other}")
    typer.echo(f"Moved: {result.files_moved}")
    typer.echo(f"Replaced: {result.files_replaced}")
    typer.echo(f"Ignored: {result.files_ignored}")
    typer.echo(f"Failed: {result.files_failed}")

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
