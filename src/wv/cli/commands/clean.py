from pathlib import Path
from typing import Annotated

import typer

from wv.cli.presentation import render_command_summary
from wv.cli.runtime import get_logger, get_runtime
from wv.use_cases.clean.bursts import CleanBurstsInput
from wv.use_cases.clean.bursts import run as run_clean_bursts
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
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting clean.corrupted. Source: %s. Output: %s. Dry run: %s.",
        source,
        output,
        "yes" if dry_run else "no",
    )

    result = run_clean_corrupted(
        CleanCorruptedInput(source=source, output=output, dry_run=dry_run)
    )

    render_command_summary(
        runtime,
        title="Clean Corrupted Summary",
        message=(
            "Corrupted image cleanup finished."
            if result.files_failed == 0
            else "Corrupted image cleanup finished with failures."
        ),
        rows=[
            ("Source", source),
            ("Destination", result.destination),
            ("Dry run", "yes" if result.dry_run else "no"),
            ("Discovered", result.files_discovered),
            ("Corrupted", result.files_corrupted),
            ("Moved", result.files_moved),
            ("Ignored", result.files_ignored),
            ("Failed", result.files_failed),
        ],
        level_name="OK" if result.files_failed == 0 else "ERROR",
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
            help="Minimum average grayscale brightness required to flag an image as overexposed.",
        ),
    ] = 200.0,
    std_threshold: Annotated[
        float,
        typer.Option(
            "--std-threshold",
            help="Maximum grayscale standard deviation allowed when treating a bright image as uniformly overexposed.",
        ),
    ] = 25.0,
    high_level: Annotated[
        int,
        typer.Option(
            "--high-level",
            help="Grayscale value used as the cutoff for counting near-white pixels in the image histogram.",
        ),
    ] = 220,
    ptc_high_threshold: Annotated[
        float,
        typer.Option(
            "--ptc-high-threshold",
            help="Minimum fraction of pixels at or above --high-level required to flag an image as overexposed.",
        ),
    ] = 0.60,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    """Move likely washed-out infrared images into an ignored/overexposed folder."""
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting clean.overexposed-ir. Source: %s. Output: %s. Dry run: %s.",
        source,
        output,
        "yes" if dry_run else "no",
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

    render_command_summary(
        runtime,
        title="Clean Overexposed IR Summary",
        message=(
            "Overexposed IR cleanup finished."
            if result.files_failed == 0
            else "Overexposed IR cleanup finished with failures."
        ),
        rows=[
            ("Source", source),
            ("Destination", result.destination),
            ("Dry run", "yes" if result.dry_run else "no"),
            ("Discovered", result.files_discovered),
            ("Overexposed", result.files_overexposed),
            ("Moved", result.files_moved),
            ("Ignored", result.files_ignored),
            ("Failed", result.files_failed),
        ],
        level_name="OK" if result.files_failed == 0 else "ERROR",
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
            help="Maximum time gap in seconds between consecutive images for grouping them into the same burst.",
        ),
    ] = 60,
    similarity_threshold: Annotated[
        int,
        typer.Option(
            "--similarity-threshold",
            help="Maximum perceptual hash distance for treating images inside a burst as visually similar.",
        ),
    ] = 5,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
    """Keep the best images from near-duplicate bursts and move the rest into ignored/bursts."""
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting clean.bursts. Source: %s. Output: %s. Dry run: %s.",
        source,
        output,
        "yes" if dry_run else "no",
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

    render_command_summary(
        runtime,
        title="Clean Bursts Summary",
        message=(
            "Burst cleanup finished."
            if result.files_failed == 0
            else "Burst cleanup finished with failures."
        ),
        rows=[
            ("Source", source),
            ("Destination", result.destination),
            ("Dry run", "yes" if result.dry_run else "no"),
            ("Discovered", result.files_discovered),
            ("Bursts", result.files_bursts),
            ("Reduced", result.files_reduced),
            ("Moved", result.files_moved),
            ("Ignored", result.files_ignored),
            ("Failed", result.files_failed),
        ],
        level_name="OK" if result.files_failed == 0 else "ERROR",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
