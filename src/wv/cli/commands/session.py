from typing import Annotated

import typer

from wv.cli.table import print_table
from wv.core.logger import get_logger
from wv.domain.session import INGEST_STATUSES
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

app = typer.Typer(help="Inspect and process managed ingest sessions.")
clean_app = typer.Typer(help="Run ordered cleanup stages for an ingested session.")
app.add_typer(clean_app, name="clean")
detect_app = typer.Typer(help="Run the ordered content-detection stage for an ingested session.")
app.add_typer(detect_app, name="detect")

logger = get_logger(__name__)


@app.command("list")
def list_sessions(
    area: Annotated[
        str | None,
        typer.Option("--area", help="Show only sessions in this monitoring area."),
    ] = None,
    monitoring_site: Annotated[
        str | None,
        typer.Option(
            "--monitoring-site",
            help="Show only sessions for this monitoring-site ID.",
        ),
    ] = None,
    ingest_status: Annotated[
        str | None,
        typer.Option(
            "--ingest-status",
            help=f"Show only sessions with status: {', '.join(INGEST_STATUSES)}.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Maximum number of sessions to show."),
    ] = 20,
):
    """List incomplete sessions first, then completed sessions by recency."""
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

    print_table(
        ["SESSION ID", "STARTED AT", "SITE ID", "PROCESSING STATUS"],
        (
            (item.id, item.started_at, item.monitoring_site_id, item.processing_status)
            for item in result.items
        ),
        ratios=[3, 3, 2, 2],
    )

    return None


@app.command("status")
def session_status(
    session_id: Annotated[
        str,
        typer.Argument(help="Ingest session ID in the active workspace."),
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
        typer.Argument(help="Completed ingest session ID in the active workspace."),
    ],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Scan images without moving files or updating process and inventory state.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Recover an interrupted attempt after reconciling moved files with session inventory.",
        ),
    ] = False,
):
    """Run the first managed stage and move unreadable images to ignored/corrupted."""
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
        typer.Argument(help="Completed ingest session ID after the corrupted stage."),
    ],
    mean_threshold: Annotated[
        float | None,
        typer.Option(
            "--mean-threshold",
            min=0.0,
            max=255.0,
            help="Override the workspace grayscale mean for a new stage; retries use the recorded value.",
        ),
    ] = None,
    std_threshold: Annotated[
        float | None,
        typer.Option(
            "--std-threshold",
            min=0.0,
            help="Override workspace grayscale deviation for a new stage; retries use the recorded value.",
        ),
    ] = None,
    high_level: Annotated[
        int | None,
        typer.Option(
            "--high-level",
            min=0,
            max=255,
            help="Override the workspace near-white cutoff for a new stage; retries use the recorded value.",
        ),
    ] = None,
    pct_high_threshold: Annotated[
        float | None,
        typer.Option(
            "--pct-high-threshold",
            min=0.0,
            max=1.0,
            help="Override the workspace near-white fraction for a new stage; retries use the recorded value.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Analyze images without moving files or updating process and inventory state.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Recover an interrupted attempt after reconciling moved files with session inventory.",
        ),
    ] = False,
):
    """Run the second managed stage and move likely overexposed IR images."""
    try:
        result = run_clean_overexposed_ir(
            SessionCleanOverexposedIrInput(
                session_id=session_id,
                mean_threshold=mean_threshold,
                std_threshold=std_threshold,
                high_level=high_level,
                pct_high_threshold=pct_high_threshold,
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
        typer.Argument(help="Completed ingest session ID after the overexposed-IR stage."),
    ],
    burst_gap_threshold: Annotated[
        int | None,
        typer.Option(
            "--burst-gap-threshold",
            min=0,
            help="Override the workspace burst gap for a new stage; retries use the recorded value.",
        ),
    ] = None,
    similarity_threshold: Annotated[
        int | None,
        typer.Option(
            "--similarity-threshold",
            min=0,
            max=64,
            help="Override workspace hash similarity for a new stage; retries use the recorded value.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Build the reduction plan without moving files or updating process and inventory state.",
        ),
    ] = False,
    recover: Annotated[
        bool,
        typer.Option(
            "--recover",
            help="Resume an interrupted attempt from its saved reduction plan.",
        ),
    ] = False,
):
    """Run the third managed stage and reduce similar image bursts."""
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
        typer.Argument(help="Completed ingest session ID after corrupted and overexposed-IR cleanup."),
    ],
    model: Annotated[str | None, typer.Option(help="Override the workspace model for a new stage; retries use the recorded value.")] = None,
    speciesnet_model: Annotated[str | None, typer.Option(help="Override the workspace SpeciesNet model for a new stage; retries use the recorded value.")] = None,
    batch_size: Annotated[
        int | None,
        typer.Option(
            "--batch-size",
            min=1,
            help="Override workspace inference batch size for a new stage; retries use the recorded value.",
        ),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview classifications without moving files or updating the database; a new plan still runs inference.")] = False,
    recover: Annotated[bool, typer.Option("--recover", help="Resume an interrupted attempt from its saved inference plan without rerunning inference.")] = False,
):
    """Classify managed images as animal, human, vehicle, domestic, empty, or other."""
    try:
        result = run_detect_content(
            SessionDetectContentInput(
                session_id=session_id,
                model=model,
                speciesnet_model=speciesnet_model,
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
        "Finished managed detection for %s: evaluated=%s animal=%s human=%s vehicle=%s domestic=%s empty=%s other=%s moved=%s failed=%s%s",
        result.session_id,
        result.files_evaluated,
        result.files_animal,
        result.files_human,
        result.files_vehicle,
        result.files_domestic,
        result.files_empty,
        result.files_other,
        result.files_moved,
        result.files_failed,
        " (dry run)" if dry_run else "",
    )
    if result.files_failed > 0:
        raise typer.Exit(code=1)
    return None
