from typing import Annotated

import typer

from wv.cli.completion import complete_detection_label, complete_reviewable_session_id
from wv.gui.favorites.app import launch_favorites_app
from wv.gui.review_detection.app import launch_review_detection_app
from wv.gui.review_detection_preview.app import launch_review_detection_preview_app
from wv.core.session import DETECTION_LABELS, normalize_detection_label

app = typer.Typer(help="Launch interactive review tools for managed sessions.")


@app.command("review-detection")
def review_detection(
    session_id: Annotated[
        str,
        typer.Argument(
            help="Managed session ID with completed content detection.",
            autocompletion=complete_reviewable_session_id,
        ),
    ],
    detection: Annotated[
        str,
        typer.Option(
            "--detection",
            help="Bucket to review: animal, human, vehicle, domestic, empty, or other.",
            case_sensitive=False,
            autocompletion=complete_detection_label,
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


@app.command("review-detection-preview")
def review_detection_preview(
    session_id: Annotated[
        str,
        typer.Argument(
            help="Managed session ID with completed content detection.",
            autocompletion=complete_reviewable_session_id,
        ),
    ],
    include_reviewed: Annotated[
        bool,
        typer.Option(
            "--include-reviewed",
            help="Include already verified images, which remain editable.",
        ),
    ] = False,
):
    """Preview session-wide keyboard detection review."""
    launch_review_detection_preview_app(
        session_id=session_id,
        include_reviewed=include_reviewed,
    )
    return None


@app.command("favorites")
def favorites(
    session_id: Annotated[
        str,
        typer.Argument(
            help="Managed session ID with completed content detection.",
            autocompletion=complete_reviewable_session_id,
        ),
    ],
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
