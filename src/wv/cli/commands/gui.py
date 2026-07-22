from pathlib import Path
from typing import Annotated

import typer

from wv.gui.research_grade.app import launch_research_grade_app
from wv.gui.review.app import launch_review_app
from wv.use_cases.review import REVIEW_LABELS, normalize_review_label

app = typer.Typer(help="Launch interactive GUI review tools.")


@app.command("review")
def review(
    session_path: Annotated[
        Path,
        typer.Argument(
            help="Session/output directory containing detection/<label> folders.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    detection: Annotated[
        str,
        typer.Option(
            "--detection",
            help="Detection bucket to review.",
            case_sensitive=False,
        ),
    ],
    pending_only: Annotated[
        bool,
        typer.Option(
            "--pending-only",
            help="Only load images that do not already have Reviewed=true in EXIF metadata.",
        ),
    ] = False,
):
    """Launch the interactive reviewer for one detection bucket."""
    try:
        normalized_detection = normalize_review_label(detection)
    except ValueError as exc:
        raise typer.BadParameter(
            f"Unknown detection label '{detection}'. Expected one of: {', '.join(REVIEW_LABELS)}."
        ) from exc

    launch_review_app(
        session_path=session_path,
        detection_label=normalized_detection,
        pending_only=pending_only,
    )

    return None


@app.command("research-grade")
def research_grade(
    session_path: Annotated[
        Path,
        typer.Argument(
            help="Session/output directory containing detection/animal.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    pending_only: Annotated[
        bool,
        typer.Option(
            "--pending-only",
            help="Only load images that do not already have a Research_Grade EXIF value.",
        ),
    ] = False,
):
    """Launch the interactive research-grade reviewer for animal detections."""
    launch_research_grade_app(
        session_path=session_path,
        pending_only=pending_only,
    )

    return None
