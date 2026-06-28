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
    burst_gap_threshold: Annotated[int, typer.Option("--burst-gap-threshold")] = 60,
    similarity_threshold: Annotated[int, typer.Option("--similarity-threshold")] = 5,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the clean operation without moving any files.",
        ),
    ] = False,
):
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
