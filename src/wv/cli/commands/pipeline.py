from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.core.session import get_init_path
from wv.use_cases.clean.overexposed_ir import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.use_cases.detect.content import DEFAULT_CONFIDENCE_THRESHOLD, DEFAULT_MODEL
from wv.use_cases.pipeline.preprocess import PipelinePreprocessInput
from wv.use_cases.pipeline.preprocess import run as run_pipeline_preprocess

app = typer.Typer(help="Run image preprocessing pipeline steps.")

logger = get_logger(__name__)


@app.command("preprocess")
def pipeline_preprocess(
    session_path: Annotated[
        Path,
        typer.Argument(
            help="Ingested session directory matching YYYYMMDD_HHMMSS__CAMERA.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    mean_threshold: Annotated[
        float,
        typer.Option(
            "--mean-threshold",
            min=0.0,
            max=255.0,
            help="Minimum average grayscale brightness required to flag an image as overexposed.",
        ),
    ] = DEFAULT_MEAN_THRESHOLD,
    std_threshold: Annotated[
        float,
        typer.Option(
            "--std-threshold",
            min=0.0,
            help="Maximum grayscale standard deviation allowed when treating a bright image as uniformly overexposed.",
        ),
    ] = DEFAULT_STD_THRESHOLD,
    high_level: Annotated[
        int,
        typer.Option(
            "--high-level",
            min=0,
            max=255,
            help="Grayscale value used as the cutoff for counting near-white pixels in the image histogram.",
        ),
    ] = DEFAULT_HIGH_LEVEL,
    ptc_high_threshold: Annotated[
        float,
        typer.Option(
            "--ptc-high-threshold",
            min=0.0,
            max=1.0,
            help="Minimum fraction of pixels at or above --high-level required to flag an image as overexposed.",
        ),
    ] = DEFAULT_PTC_HIGH_THRESHOLD,
    burst_gap_threshold: Annotated[
        int,
        typer.Option(
            "--burst-gap-threshold",
            min=0,
            help="Maximum time gap in seconds between consecutive images for grouping them into the same burst.",
        ),
    ] = 60,
    similarity_threshold: Annotated[
        int,
        typer.Option(
            "--similarity-threshold",
            min=0,
            help="Maximum perceptual hash distance for treating images inside a burst as visually similar.",
        ),
    ] = 5,
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
            help="Preview the preprocessing pipeline without moving files or writing metadata.",
        ),
    ] = False,
):
    """Run corrupted cleanup, overexposed cleanup, burst reduction, and content detection for one ingested session."""
    init_path = get_init_path(session_path)
    logger.info(
        "Starting preprocess pipeline for %s using %s (dry_run=%s)",
        display_path(session_path),
        display_path(init_path),
        dry_run,
    )

    try:
        result = run_pipeline_preprocess(
            PipelinePreprocessInput(
                session_path=session_path,
                mean_threshold=mean_threshold,
                std_threshold=std_threshold,
                high_level=high_level,
                ptc_high_threshold=ptc_high_threshold,
                burst_gap_threshold=burst_gap_threshold,
                similarity_threshold=similarity_threshold,
                model=model,
                confidence_threshold=confidence_threshold,
                batch_size=batch_size,
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_path") from exc

    logger.done(
        "Finished preprocess pipeline for %s: corrupted=%s overexposed=%s reduced=%s evaluated=%s moved=%s failed=%s remaining_in_init=%s%s",
        display_path(result.session_path),
        result.corrupted_result.files_corrupted,
        result.overexposed_result.files_overexposed,
        result.bursts_result.files_reduced,
        result.detect_result.files_evaluated,
        result.detect_result.files_moved,
        result.files_failed,
        result.files_remaining_in_init,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
