from typing import Annotated

import typer

from wv.gui.favorites.app import launch_favorites_app
from wv.gui.review_detection.app import launch_review_detection_app
from wv.core.session import DETECTION_LABELS, normalize_detection_label

app = typer.Typer(help="Launch interactive review tools for managed sessions.")


@app.command("review-detection")
def review_detection(
    session_id: Annotated[str, typer.Argument(help="Managed session ID with completed content detection.")],
    detection: Annotated[
        str,
        typer.Option(
            "--detection",
            help="Bucket to review: animal, human, vehicle, empty, or other.",
            case_sensitive=False,
        ),
    ],
    pending_only: Annotated[
        bool,
        typer.Option(
            "--pending-only",
            help="Load only images whose detection label has not been reviewed.",
        ),
    ] = False,
):
    """Review and relabel images in one completed detection bucket."""
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
    session_id: Annotated[str, typer.Argument(help="Managed session ID with completed content detection.")],
    pending_only: Annotated[
        bool,
        typer.Option(
            "--pending-only",
            help="Load only animal images whose favorite status has not been reviewed.",
        ),
    ] = False,
):
    """Review favorite status for animal detections."""
    launch_favorites_app(
        session_id=session_id,
        pending_only=pending_only,
    )

    return None
