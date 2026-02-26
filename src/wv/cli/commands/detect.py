import typer
from typing import Annotated

from wv.core.logging import get_logger
from wv.core.prompt import prompt_path
from wv.handlers.overexposed_ir_detector import OverexposedIRDetectorHandler

app = typer.Typer(help="Photo detection commands")

log = get_logger("DetectCommand")


@app.command("overexposed-ir")
def detect_overexposed_ir(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Perform a dry run without moving files")
    ] = False,
    mean_threshold: Annotated[
        float,
        typer.Option("--mean-threshold", help="Grayscale mean threshold (0..255)"),
    ] = 200.0,
    std_threshold: Annotated[
        float,
        typer.Option(
            "--std-threshold", help="Grayscale standard deviation threshold (0..255)"
        ),
    ] = 25.0,
    high_level: Annotated[
        int,
        typer.Option(
            "--high-level", help="Gray level considered 'near white' (0..255)"
        ),
    ] = 220,
    pct_high_threshold: Annotated[
        float,
        typer.Option(
            "--pct-high-threshold",
            help="Fraction of near white pixels threshold (0..1)",
        ),
    ] = 0.60,
):
    input_path = prompt_path("Enter the input folder path: ").strip()

    output_path = prompt_path(
        "Enter the output folder path (ignored if --dry-run): "
    ).strip()

    handler = OverexposedIRDetectorHandler(
        input_path=input_path,
        output_path=output_path,
        mean_threshold=mean_threshold,
        std_threshold=std_threshold,
        high_level=high_level,
        pct_high_threshold=pct_high_threshold,
    )

    result = handler.run(dry_run=dry_run)

    log.info(
        f"Overexposed IR detection completed. Total: {result.total_files}, Overexposed: {result.overexposed_files}, Moved: {result.moved_files}, Skipped: {result.skipped_files}, Failed: {result.failed_files}"
    )


@app.command("duplicates")
def detect_duplicates(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Perform a dry run without moving files")
    ] = False,
):

    return None
