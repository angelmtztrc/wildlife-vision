from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedInput
from wv.use_cases.session.clean_corrupted import run as run_clean_corrupted
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrInput,
)
from wv.use_cases.session.clean_overexposed_ir import run as run_clean_overexposed_ir
from wv.use_cases.session.clean_bursts import SessionCleanBurstsInput
from wv.use_cases.session.clean_bursts import run as run_clean_bursts
from wv.use_cases.clean.bursts import (
    DEFAULT_BURST_GAP_THRESHOLD,
    DEFAULT_SIMILARITY_THRESHOLD,
)
from wv.use_cases.clean.overexposed_ir import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.use_cases.detect.content import (
    DEFAULT_AMBIGUITY_GAP,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL,
)
from wv.use_cases.session.detect_content import (
    DEFAULT_BATCH_SIZE,
    SessionDetectContentInput,
)
from wv.use_cases.session.detect_content import run as run_detect_content
from wv.use_cases.session._shared import SessionProcessError

app = typer.Typer(help="Run database-tracked processing for ingested sessions.")
clean_app = typer.Typer(help="Run ordered cleanup stages for an ingested session.")
app.add_typer(clean_app, name="clean")
detect_app = typer.Typer(help="Run ordered detection stages for an ingested session.")
app.add_typer(detect_app, name="detect")

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
    except SessionProcessError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
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


@clean_app.command("bursts")
def clean_bursts(
    session_id: Annotated[
        str,
        typer.Argument(help="ID of an ingested session in the active workspace."),
    ],
    burst_gap_threshold: Annotated[
        int,
        typer.Option(
            "--burst-gap-threshold",
            min=0,
            help="Maximum time gap in seconds between consecutive burst images.",
        ),
    ] = DEFAULT_BURST_GAP_THRESHOLD,
    similarity_threshold: Annotated[
        int,
        typer.Option(
            "--similarity-threshold",
            min=0,
            max=64,
            help="Maximum 64-bit perceptual-hash distance for similar images.",
        ),
    ] = DEFAULT_SIMILARITY_THRESHOLD,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview burst cleanup without moving files or updating the database.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Resume an interrupted burst-cleanup attempt using its saved plan.",
        ),
    ] = False,
):
    """Reduce burst images while recording an immutable session decision plan."""
    try:
        result = run_clean_bursts(
            SessionCleanBurstsInput(
                session_id=session_id,
                burst_gap_threshold=burst_gap_threshold,
                similarity_threshold=similarity_threshold,
                dry_run=dry_run,
                recover=recover,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed burst cleanup for %s: bursts=%s reduced=%s moved=%s failed=%s%s",
        result.session_id,
        result.clean_result.files_bursts,
        result.clean_result.files_reduced,
        result.clean_result.files_moved,
        result.clean_result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.clean_result.files_failed > 0:
        raise typer.Exit(code=1)

    return None


@detect_app.command("content")
def detect_content(
    session_id: Annotated[
        str,
        typer.Argument(help="ID of an ingested session in the active workspace."),
    ],
    model: Annotated[str, typer.Option(help="MegaDetector model name or path.")] = DEFAULT_MODEL,
    confidence_threshold: Annotated[
        float,
        typer.Option("--confidence-threshold", min=0.0, max=1.0),
    ] = DEFAULT_CONFIDENCE_THRESHOLD,
    ambiguity_gap: Annotated[
        float,
        typer.Option("--ambiguity-gap", min=0.0, max=1.0),
    ] = DEFAULT_AMBIGUITY_GAP,
    batch_size: Annotated[int, typer.Option("--batch-size", min=1)] = DEFAULT_BATCH_SIZE,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    recover: Annotated[bool, typer.Option("--recover")] = False,
):
    """Detect session content using an immutable, recoverable inference plan."""
    try:
        result = run_detect_content(
            SessionDetectContentInput(
                session_id=session_id,
                model=model,
                confidence_threshold=confidence_threshold,
                ambiguity_gap=ambiguity_gap,
                batch_size=batch_size,
                dry_run=dry_run,
                recover=recover,
            )
        )
    except SessionProcessError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed detection for %s: evaluated=%s animal=%s human=%s vehicle=%s empty=%s other=%s moved=%s failed=%s%s",
        result.session_id,
        result.detect_result.files_evaluated,
        result.detect_result.files_animal,
        result.detect_result.files_human,
        result.detect_result.files_vehicle,
        result.detect_result.files_empty,
        result.detect_result.files_other,
        result.detect_result.files_moved,
        result.detect_result.files_failed,
        " (dry run)" if dry_run else "",
    )
    if result.detect_result.files_failed > 0:
        raise typer.Exit(code=1)
    return None
