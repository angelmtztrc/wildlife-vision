import typer
from typing import Annotated

from wv import config
from wv.core.prompt import prompt_path, prompt_choices
from wv.core.logging import get_logger

from wv.handlers.photo_organiser import PhotoOrganiserHandler

app = typer.Typer(help="Photo organisation commands")

log = get_logger("OrganiseCommand")


@app.command("photos")
def organise_photos(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Perform a dry run without moving files")
    ] = False,
):

    input_path = prompt_path("Enter the input folder path: ").strip()

    available_camera_locations = config.get_camera_locations_ids()
    camera_location = prompt_choices(
        "Enter the location of the camera: ", available_camera_locations
    )
    output_path = prompt_path("Enter the output folder path: ").strip()

    handler = PhotoOrganiserHandler(input_path, camera_location, output_path)

    result = handler.run(dry_run=dry_run)

    log.info(
        f"Photo organisation completed. Processed: {result.processed_files}, Skipped: {result.skipped_files}, Failed: {result.failed_files}"
    )
