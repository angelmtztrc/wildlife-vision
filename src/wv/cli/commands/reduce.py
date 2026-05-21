import typer
from typing import Annotated


from wv.core.logging import get_logger
from wv.core.prompt import prompt_path
from wv.handlers.burst_reducer import BurstReducerHandler

app = typer.Typer(help="Photos reduction commands")

log = get_logger("ReduceCommand")


@app.command("bursts")
def reduce_bursts(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Perform a dry run without moving files")
    ] = False,
    burst_gap_threshold: Annotated[
        int,
        typer.Option(
            "--gap-threshold",
            help="Maximum gap in seconds between photos to be considered part of the same burst",
        ),
    ] = 60,
    similarity_threshold: Annotated[
        int,
        typer.Option(
            "--similarity-threshold",
            min=0,
            help="Maximum perceptual hash distance between photos to be considered similar",
        ),
    ] = 5,
):
    input_path = prompt_path("Enter the input folder path: ").strip()
    output_path = prompt_path(
        "Enter the output folder path (ignored if --dry-run): "
    ).strip()

    handler = BurstReducerHandler(
        input_path=input_path,
        burst_gap_threshold=burst_gap_threshold,
        similarity_threshold=similarity_threshold,
        output_path=output_path,
    )

    result = handler.run(dry_run=dry_run)

    log.info(
        f"Burst reduction completed. Total: {result.total_files}, Bursts: {result.total_bursts}, Kept: {result.kept_files}, Reduced: {result.reduced_files}, Moved: {result.moved_files}, Skipped: {result.skipped_files}, Failed: {result.failed_files}"
    )
