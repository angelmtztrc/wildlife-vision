import typer
from typing import Annotated, get_args

from wv.core.logging import get_logger
from wv.core.prompt import prompt_choices, prompt_path
from wv.core.metadata import AvailableDetections

from wv.handlers.detection_exporter import DetectionExporterHandler

app = typer.Typer(help="Photo export commands")

log = get_logger("ExportCommand")


@app.command("detection")
def export_by_detection(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Perform a dry run export process without actually moving the files",
        ),
    ],
):
    input_path = prompt_path("Enter the input folder path: ").strip()
    detection = prompt_choices(
        "Enter the targeted detection value: ", list(get_args(AvailableDetections))
    )
    output_path = prompt_path("Enter the output folder path: ").strip()

    handler = DetectionExporterHandler(
        input_path=input_path,
        target_detection=detection,
        output_path=output_path,
    )

    result = handler.run(dry_run=dry_run)

    log.info(
        f"Detection-based export completed. Total: {result.total_files}, Exported: {result.exported_files}, Skipped: {result.skipped_files}, Failed: {result.failed_files}"
    )
