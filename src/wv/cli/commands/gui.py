from typing import Annotated

import typer

from wv.gui.favorites.app import launch_favorites_app
from wv.gui.review_detection.app import launch_review_detection_app
from wv.core.session import DETECTION_LABELS, normalize_detection_label

app = typer.Typer(help="Launch interactive GUI review tools.")


@app.command("review-detection")
def review_detection(
    session_id: Annotated[str, typer.Argument(help="Managed session identifier.")],
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
            help="Only load images that have not been reviewed in the database.",
        ),
    ] = False,
):
    """Launch the interactive reviewer for one detection bucket."""
    try:
        normalized_detection = normalize_detection_label(detection)
    except ValueError as exc:
        raise typer.BadParameter(
            f"Unknown detection label '{detection}'. Expected one of: {', '.join(DETECTION_LABELS)}."
        ) from exc

    launch_review_detection_app(
        session_id=session_id,
        detection_label=normalized_detection,
        pending_only=pending_only,
    )

    return None


@app.command("favorites")
def favorites(
    session_id: Annotated[str, typer.Argument(help="Managed session identifier.")],
    pending_only: Annotated[
        bool,
        typer.Option(
            "--pending-only",
            help="Only load animal images that have not had their favorite state reviewed.",
        ),
    ] = False,
):
    """Launch the interactive favorites reviewer for animal detections."""
    launch_favorites_app(
        session_id=session_id,
        pending_only=pending_only,
    )

    return None
