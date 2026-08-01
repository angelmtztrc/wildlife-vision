from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedInput
from wv.use_cases.session.clean_corrupted import run as run_clean_corrupted
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrInput,
)
from wv.use_cases.session.clean_overexposed_ir import run as run_clean_overexposed_ir
from wv.use_cases.clean.overexposed_ir import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)

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


@clean_app.command("overexposed-ir")
def clean_overexposed_ir(
    session_id: Annotated[
        str,
        typer.Argument(help="ID of an ingested session in the active workspace."),
    ],
    mean_threshold: Annotated[
        float,
        typer.Option(
            "--mean-threshold",
            min=0.0,
            max=255.0,
            help="Minimum average grayscale brightness required to flag an image as overexposed.",
        ),
    ] = DEFAULT_MEAN_THRESHOLD,
    std_threshold: Annotated[
        float,
        typer.Option(
            "--std-threshold",
            min=0.0,
            help="Maximum grayscale standard deviation for bright, uniform images.",
        ),
    ] = DEFAULT_STD_THRESHOLD,
    high_level: Annotated[
        int,
        typer.Option(
            "--high-level",
            min=0,
            max=255,
            help="Grayscale cutoff used to count near-white pixels.",
        ),
    ] = DEFAULT_HIGH_LEVEL,
    ptc_high_threshold: Annotated[
        float,
        typer.Option(
            "--ptc-high-threshold",
            min=0.0,
            max=1.0,
            help="Minimum near-white pixel fraction required to flag an image.",
        ),
    ] = DEFAULT_PTC_HIGH_THRESHOLD,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview overexposed cleanup without moving files or updating the database.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Resume an interrupted overexposed-cleanup attempt after reconciling its inventory.",
        ),
    ] = False,
):
    """Clean overexposed images while recording ordered session-process state."""
    try:
        result = run_clean_overexposed_ir(
            SessionCleanOverexposedIrInput(
                session_id=session_id,
                mean_threshold=mean_threshold,
                std_threshold=std_threshold,
                high_level=high_level,
                ptc_high_threshold=ptc_high_threshold,
                dry_run=dry_run,
                recover=recover,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed overexposed cleanup for %s: processed=%s overexposed=%s moved=%s failed=%s%s",
        result.session_id,
        result.clean_result.files_processed,
        result.clean_result.files_overexposed,
        result.clean_result.files_moved,
        result.clean_result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.clean_result.files_failed > 0:
        raise typer.Exit(code=1)

    return None
