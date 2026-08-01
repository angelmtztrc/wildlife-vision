from pathlib import Path
from typing import Annotated

import typer

from wv.core.bursts import DEFAULT_BURST_GAP_THRESHOLD, DEFAULT_SIMILARITY_THRESHOLD
from wv.core.display import display_path
from wv.core.images import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.core.logger import get_logger
from wv.use_cases.clean.bursts import CleanBurstsInput
from wv.use_cases.clean.bursts import run as run_clean_bursts
from wv.use_cases.clean.corrupted import CleanCorruptedInput
from wv.use_cases.clean.corrupted import run as run_clean_corrupted
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrInput
from wv.use_cases.clean.overexposed_ir import run as run_clean_overexposed_ir

app = typer.Typer(
    help="Identify and clean corrupted, overexposed IR, and burst photos."
)

logger = get_logger(__name__)


@app.command("corrupted")
def clean_corrupted(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory to scan for image files and move corrupted photos from.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            help="Base output directory where corrupted photos are moved under ignored/corrupted.",
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
    """Detect unreadable image files and move them into an ignored/corrupted folder."""
    logger.info(
        "Starting corrupted cleanup from %s to %s (dry_run=%s)",
        display_path(source),
        display_path(output),
        dry_run,
    )

    result = run_clean_corrupted(
        CleanCorruptedInput(source=source, output=output, dry_run=dry_run)
    )

    logger.done(
        "Finished corrupted cleanup to %s: discovered=%s corrupted=%s moved=%s ignored=%s failed=%s%s",
        display_path(result.destination),
        result.files_discovered,
        result.files_corrupted,
        result.files_moved,
        result.files_ignored,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("overexposed-ir")
def clean_overexposed_ir(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory to scan for image files and move overexposed IR photos from.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            help="Base output directory where overexposed IR photos are moved under ignored/overexposed.",
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
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    """Move likely washed-out infrared images into an ignored/overexposed folder."""
    logger.info(
        "Starting overexposed IR cleanup from %s to %s (mean_threshold=%s, std_threshold=%s, high_level=%s, ptc_high_threshold=%s, dry_run=%s)",
        display_path(source),
        display_path(output),
        mean_threshold,
        std_threshold,
        high_level,
        ptc_high_threshold,
        dry_run,
    )

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

    logger.done(
        "Finished overexposed IR cleanup to %s: discovered=%s overexposed=%s moved=%s ignored=%s failed=%s%s",
        display_path(result.destination),
        result.files_discovered,
        result.files_overexposed,
        result.files_moved,
        result.files_ignored,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@app.command("bursts")
def clean_bursts(
    source: Annotated[
        Path,
        typer.Argument(
            help="Directory to scan for images and reduce burst sequences from.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            help="Base output directory where reduced burst images are moved under ignored/bursts.",
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    burst_gap_threshold: Annotated[
        int,
        typer.Option(
            "--burst-gap-threshold",
            min=0,
            help="Maximum time gap in seconds between consecutive images for grouping them into the same burst.",
        ),
    ] = DEFAULT_BURST_GAP_THRESHOLD,
    similarity_threshold: Annotated[
        int,
        typer.Option(
            "--similarity-threshold",
            min=0,
            max=64,
            help="Maximum perceptual hash distance for treating images inside a burst as visually similar.",
        ),
    ] = DEFAULT_SIMILARITY_THRESHOLD,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    """Keep the best images from near-duplicate bursts and move the rest into ignored/bursts."""
    logger.info(
        "Starting burst cleanup from %s to %s (burst_gap_threshold=%s, similarity_threshold=%s, dry_run=%s)",
        display_path(source),
        display_path(output),
        burst_gap_threshold,
        similarity_threshold,
        dry_run,
    )

    result = run_clean_bursts(
        CleanBurstsInput(
            source=source,
            output=output,
            burst_gap_threshold=burst_gap_threshold,
            similarity_threshold=similarity_threshold,
            dry_run=dry_run,
        )
    )

    logger.done(
        "Finished burst cleanup to %s: discovered=%s bursts=%s reduced=%s moved=%s ignored=%s failed=%s%s",
        display_path(result.destination),
        result.files_discovered,
        result.files_bursts,
        result.files_reduced,
        result.files_moved,
        result.files_ignored,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
