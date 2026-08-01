from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.detect.content import (
    DEFAULT_AMBIGUITY_GAP,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL,
    DetectContentInput,
)
from wv.use_cases.detect.content import run as run_detect_content

app = typer.Typer(help="Run content detection on photos.")

logger = get_logger(__name__)


@app.command("content")
def detect_content(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory containing images to evaluate with MegaDetector.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            help="Base output directory where detected images are moved into output/detection/<label>.",
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
    ambiguity_gap: Annotated[
        float,
        typer.Option(
            "--ambiguity-gap",
            min=0.0,
            max=1.0,
            help="Minimum lead over the second label required to avoid other.",
        ),
    ] = DEFAULT_AMBIGUITY_GAP,
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
    """Classify images into animal, human, vehicle, empty, or other using MegaDetector."""
    logger.info(
        "Starting content detection from %s to %s (model=%s, confidence_threshold=%s, batch_size=%s, dry_run=%s)",
        display_path(source),
        display_path(output),
        model,
        confidence_threshold,
        batch_size,
        dry_run,
    )

    result = run_detect_content(
        DetectContentInput(
            source=source,
            output=output,
            model=model,
            confidence_threshold=confidence_threshold,
            ambiguity_gap=ambiguity_gap,
            batch_size=batch_size,
            dry_run=dry_run,
        )
    )

    logger.done(
        "Finished content detection to %s: discovered=%s evaluated=%s animal=%s human=%s vehicle=%s empty=%s other=%s moved=%s replaced=%s ignored=%s failed=%s%s",
        display_path(result.destination),
        result.files_discovered,
        result.files_evaluated,
        result.files_animal,
        result.files_human,
        result.files_vehicle,
        result.files_empty,
        result.files_other,
        result.files_moved,
        result.files_replaced,
        result.files_ignored,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
