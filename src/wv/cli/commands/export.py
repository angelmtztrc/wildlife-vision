from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.session.export_favorites import ExportFavoritesInput
from wv.use_cases.session.export_favorites import run as run_export_favorites

app = typer.Typer(help="Export curated images from managed sessions.")

logger = get_logger(__name__)


@app.command("favorites")
def export_favorites(
    session_id: Annotated[str, typer.Argument(help="Managed session ID with completed content detection.")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Destination directory; defaults to exports/SESSION_ID/favorites in the active workspace.",
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Validate candidates and report planned copies and replacements without writing files.",
        ),
    ] = False,
):
    """Copy favorited animal detections from a completed managed session."""
    logger.info(
        "Starting favorite export for %s to %s (dry_run=%s)",
        session_id,
        display_path(output) if output is not None else "default export destination",
        dry_run,
    )

    try:
        result = run_export_favorites(
            ExportFavoritesInput(
                session_id=session_id,
                output=output,
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished favorite export to %s: discovered=%s candidates=%s exported=%s replaced=%s skipped=%s failed=%s%s",
        display_path(result.destination),
        result.files_discovered,
        result.files_export_candidates,
        result.files_exported,
        result.files_replaced,
        result.files_skipped,
        result.files_failed,
        " (dry run)" if result.dry_run else "",
    )

    if result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
