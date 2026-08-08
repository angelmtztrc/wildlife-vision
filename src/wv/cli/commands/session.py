from typing import Annotated

import typer

from wv.core.bursts import DEFAULT_BURST_GAP_THRESHOLD, DEFAULT_SIMILARITY_THRESHOLD
from wv.core.detection import (
    DEFAULT_AMBIGUITY_GAP,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
)
from wv.core.images import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PTC_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.core.logger import get_logger
from wv.domain.session import INGEST_STATUSES
from wv.ml.megadetector import DEFAULT_MODEL
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedInput
from wv.use_cases.session.clean_corrupted import run as run_clean_corrupted
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrInput,
)
from wv.use_cases.session.clean_overexposed_ir import run as run_clean_overexposed_ir
from wv.use_cases.session.clean_bursts import SessionCleanBurstsInput
from wv.use_cases.session.clean_bursts import run as run_clean_bursts
from wv.use_cases.session.list import ListSessionsInput
from wv.use_cases.session.list import run as run_list_sessions
from wv.use_cases.session.detect_content import (
    SessionDetectContentInput,
)
from wv.use_cases.session.detect_content import run as run_detect_content
from wv.use_cases.session.status import SessionStatusInput
from wv.use_cases.session.status import run as run_session_status
from wv.use_cases.session._shared import SessionError, SessionProcessError
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Run database-tracked processing for ingested sessions.")
clean_app = typer.Typer(help="Run ordered cleanup stages for an ingested session.")
app.add_typer(clean_app, name="clean")
detect_app = typer.Typer(help="Run ordered detection stages for an ingested session.")
app.add_typer(detect_app, name="detect")

logger = get_logger(__name__)


@app.command("list")
def list_sessions(
    area: Annotated[
        str | None,
        typer.Option("--area", help="Only show sessions in this monitoring area."),
    ] = None,
    monitoring_site: Annotated[
        str | None,
        typer.Option(
            "--monitoring-site",
            help="Only show sessions for this monitoring-site ID.",
        ),
    ] = None,
    ingest_status: Annotated[
        str | None,
        typer.Option(
            "--ingest-status",
            help=f"Only show sessions with one of: {', '.join(INGEST_STATUSES)}.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, help="Maximum number of sessions to show."),
    ] = 20,
):
    """List recent persisted ingest sessions in the active workspace."""
    try:
        result = run_list_sessions(
            ListSessionsInput(
                monitoring_area_id=area,
                monitoring_site_id=monitoring_site,
                ingest_status=ingest_status,
                limit=limit,
            )
        )
    except (WorkspaceError, SessionError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for item in result.items:
        typer.echo(
            f"{item.id}\t{item.started_at}\t{item.monitoring_site_id}\t"
            f"{item.ingest_status}"
        )

    return None


@app.command("status")
def session_status(
    session_id: Annotated[
        str,
        typer.Argument(help="ID of an ingested session in the active workspace."),
    ],
):
    """Show ingest, processing, inventory, and filesystem status for a session."""
    try:
        result = run_session_status(SessionStatusInput(session_id=session_id))
    except (WorkspaceError, SessionError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    session = result.session
    typer.echo(f"id: {session.id}")
    typer.echo(f"overall_status: {result.overall_status}")
    if result.next_action is not None and result.next_process is not None:
        next_stage = next(
            stage for stage in result.stages if stage.name == result.next_process
        )
        typer.echo(f"next_action: {result.next_action} {result.next_process}")
        typer.echo(f"next_parameters: {next_stage.parameters_json or ''}")
    else:
        typer.echo("next_action: none")
        typer.echo("next_parameters:")
    typer.echo(f"monitoring_site: {session.monitoring_site_id}")
    typer.echo(f"monitoring_area: {result.monitoring_area_id}")
    typer.echo(f"source_path: {session.source_path}")
    typer.echo(f"mode: {session.mode}")
    typer.echo(f"recursive: {str(session.recursive).lower()}")
    typer.echo(f"started_at: {session.started_at}")
    typer.echo(f"completed_at: {session.completed_at or ''}")
    typer.echo(f"ingest_status: {session.ingest_status}")
    typer.echo(f"ingest_failure: {session.failure_message or ''}")
    typer.echo(f"ingest.files_discovered: {session.files_discovered}")
    typer.echo(f"ingest.files_copied: {session.files_copied}")
    typer.echo(f"ingest.files_deleted: {session.files_deleted}")
    typer.echo(f"ingest.files_ignored: {session.files_ignored}")
    typer.echo(f"ingest.files_failed: {session.files_failed}")
    typer.echo(f"ingest.files_replaced: {session.files_replaced}")

    if result.filesystem is not None:
        typer.echo(f"filesystem_status: {result.filesystem.status}")
        typer.echo(f"session_path: {result.filesystem.session_path}")
        typer.echo(f"init_path: {result.filesystem.init_path}")
        typer.echo(f"filesystem_message: {result.filesystem.message or ''}")

    for item in result.inventory:
        typer.echo(f"inventory.{item.state}: {item.count}")

    for stage in result.stages:
        prefix = f"process.{stage.name}"
        typer.echo(f"{prefix}.status: {stage.status}")
        typer.echo(f"{prefix}.attempts: {stage.attempt_count}")
        typer.echo(f"{prefix}.started_at: {stage.started_at or ''}")
        typer.echo(f"{prefix}.completed_at: {stage.completed_at or ''}")
        typer.echo(f"{prefix}.failure: {stage.failure_message or ''}")
        typer.echo(f"{prefix}.files_discovered: {stage.files_discovered}")
        typer.echo(f"{prefix}.files_processed: {stage.files_processed}")
        typer.echo(f"{prefix}.files_selected: {stage.files_selected}")
        typer.echo(f"{prefix}.files_moved: {stage.files_moved}")
        typer.echo(f"{prefix}.files_ignored: {stage.files_ignored}")
        typer.echo(f"{prefix}.files_failed: {stage.files_failed}")
        typer.echo(f"{prefix}.bursts: {stage.bursts_count}")
        typer.echo(f"{prefix}.parameters: {stage.parameters_json or ''}")

    return None


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
        result.files_corrupted,
        result.files_moved,
        result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.files_failed > 0:
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
    except SessionProcessError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed overexposed cleanup for %s: processed=%s overexposed=%s moved=%s failed=%s%s",
        result.session_id,
        result.files_processed,
        result.files_overexposed,
        result.files_moved,
        result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.files_failed > 0:
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
    except SessionProcessError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise typer.BadParameter(str(exc), param_hint="session_id") from exc

    logger.done(
        "Finished managed burst cleanup for %s: bursts=%s reduced=%s moved=%s failed=%s%s",
        result.session_id,
        result.files_bursts,
        result.files_reduced,
        result.files_moved,
        result.files_failed,
        " (dry run)" if dry_run else "",
    )

    if result.files_failed > 0:
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
    batch_size: Annotated[
        int | None,
        typer.Option(
            "--batch-size",
            min=1,
            help="Detector inference batch size; defaults to 4 for new sessions and reuses the recorded value on retries.",
        ),
    ] = None,
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
        result.files_evaluated,
        result.files_animal,
        result.files_human,
        result.files_vehicle,
        result.files_empty,
        result.files_other,
        result.files_moved,
        result.files_failed,
        " (dry run)" if dry_run else "",
    )
    if result.files_failed > 0:
        raise typer.Exit(code=1)
    return None
