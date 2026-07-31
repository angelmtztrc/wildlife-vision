from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedInput
from wv.use_cases.session.clean_corrupted import run as run_clean_corrupted

app = typer.Typer(help="Run database-tracked processing for ingested sessions.")
clean_app = typer.Typer(help="Run ordered cleanup stages for an ingested session.")
app.add_typer(clean_app, name="clean")

logger = get_logger(__name__)


@clean_app.command("corrupted")
def clean_corrupted(
    session_id: Annotated[
        str,
        typer.Argument(help="ID of an ingested session in the active workspace."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview corrupted cleanup without moving files or updating the database.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Resume an interrupted corrupted-cleanup attempt after reconciling its inventory.",
        ),
    ] = False,
):
    """Clean corrupted images while recording ordered session-process state."""
    try:
        result = run_clean_corrupted(
            SessionCleanCorruptedInput(
                session_id=session_id,
                dry_run=dry_run,
                recover=recover,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed corrupted cleanup for %s: corrupted=%s moved=%s failed=%s%s",
        result.session_id,
        result.clean_result.files_corrupted,
        result.clean_result.files_moved,
        result.clean_result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.clean_result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
