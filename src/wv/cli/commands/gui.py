from typing import Annotated

import typer

from wv.core.prompt import prompt_path

from wv.gui.detection_triage.app import DetectionTriageApp

app = typer.Typer(help="GUI commands")


@app.command("detection-triage")
def detection_triage(
    max_files_per_session: Annotated[
        int,
        typer.Option(
            "--max-files-per-session",
            help="Maximum number of files to process in one session (0 for no limit)",
        ),
    ] = 500,
    include_detected: Annotated[
        bool,
        typer.Option(
            "--include-detected",
            help="Include already detected files in the triage session",
        ),
    ] = False,
):
    input_path = prompt_path("Enter the input folder path: ").strip()

    DetectionTriageApp(input_path, max_files_per_session, include_detected).run()
