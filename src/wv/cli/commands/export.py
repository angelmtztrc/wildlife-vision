from pathlib import Path
from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.export.research_grade import ExportResearchGradeInput
from wv.use_cases.export.research_grade import run as run_export_research_grade

app = typer.Typer(help="Export curated images.")

logger = get_logger(__name__)


@app.command("research-grade")
def export_research_grade(
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
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Destination directory for exported research-grade images.",
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview the export operation without copying any files.",
        ),
    ] = False,
):
    """Copy animal detections marked Research_Grade=true into the export folder."""
    logger.info(
        "Starting research-grade export from %s to %s (dry_run=%s)",
        display_path(session_path),
        display_path(output) if output is not None else "default export destination",
        dry_run,
    )

    try:
        result = run_export_research_grade(
            ExportResearchGradeInput(
                session_path=session_path,
                output=output,
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_path") from exc

    logger.done(
        "Finished research-grade export to %s: discovered=%s candidates=%s exported=%s replaced=%s skipped=%s failed=%s%s",
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
