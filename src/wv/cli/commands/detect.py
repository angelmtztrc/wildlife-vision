from pathlib import Path
from typing import Annotated

import typer

from wv.cli.presentation import render_command_summary
from wv.cli.runtime import get_logger, get_runtime
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
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting detect.content. Source: %s. Output: %s. Model: %s. Confidence threshold: %s. Batch size: %s. Dry run: %s.",
        source,
        output,
        model,
        confidence_threshold,
        batch_size,
        "yes" if dry_run else "no",
    )

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

    render_command_summary(
        runtime,
        title="Detect Content Summary",
        message=(
            "Content detection finished."
            if result.files_failed == 0
            else "Content detection finished with failures."
        ),
        rows=[
            ("Source", source),
            ("Destination", result.destination),
            ("Model", model),
            ("Confidence threshold", confidence_threshold),
            ("Batch size", batch_size),
            ("Dry run", "yes" if result.dry_run else "no"),
            ("Discovered", result.files_discovered),
            ("Evaluated", result.files_evaluated),
            ("Animal", result.files_animal),
            ("Human", result.files_human),
            ("Vehicle", result.files_vehicle),
            ("Empty", result.files_empty),
            ("Other", result.files_other),
            ("Moved", result.files_moved),
            ("Replaced", result.files_replaced),
            ("Ignored", result.files_ignored),
            ("Failed", result.files_failed),
        ],
        level_name="OK" if result.files_failed == 0 else "ERROR",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
