from typing import Annotated

import typer

from wv.core.logger import get_logger
from wv.use_cases.pipeline.run import PipelineRunError, PipelineRunInput
from wv.use_cases.pipeline.run import run as run_pipeline
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.list import ListSessionsInput
from wv.use_cases.session.list import run as run_list_sessions
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Run database-tracked preprocessing for ingested sessions.")
logger = get_logger(__name__)


def _complete_session(incomplete: str) -> list[str]:
    try:
        return [
            session.id
            for session in run_list_sessions(ListSessionsInput(limit=100)).items
            if session.id.startswith(incomplete)
        ]
    except (SessionError, WorkspaceError):
        return []


@app.command("run")
def run(
    session_id: Annotated[
        str,
        typer.Argument(
            help="ID of an ingested session.",
            autocompletion=_complete_session,
        ),
    ],
    recover: Annotated[
        bool,
        typer.Option("--recover", help="Recover an interrupted in-progress stage."),
    ] = False,
    next_only: Annotated[
        bool,
        typer.Option("--next", help="Run exactly one eligible stage."),
    ] = False,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Run inclusively through: corrupted, overexposed-ir, bursts, detect-content."),
    ] = None,
    mean_threshold: Annotated[float | None, typer.Option("--mean-threshold", min=0.0, max=255.0, help="Minimum average grayscale brightness for overexposure.")] = None,
    std_threshold: Annotated[float | None, typer.Option("--std-threshold", min=0.0, help="Maximum grayscale deviation for overexposure.")] = None,
    high_level: Annotated[int | None, typer.Option("--high-level", min=0, max=255, help="Near-white grayscale cutoff.")] = None,
    pct_high_threshold: Annotated[float | None, typer.Option("--pct-high-threshold", min=0.0, max=1.0, help="Minimum near-white pixel fraction.")] = None,
    burst_gap_threshold: Annotated[int | None, typer.Option("--burst-gap-threshold", min=0, help="Maximum seconds between burst images.")] = None,
    similarity_threshold: Annotated[int | None, typer.Option("--similarity-threshold", min=0, max=64, help="Maximum perceptual-hash distance.")] = None,
    model: Annotated[str | None, typer.Option("--model", help="MegaDetector model name or path.")] = None,
    confidence_threshold: Annotated[float | None, typer.Option("--confidence-threshold", min=0.0, max=1.0, help="Minimum detection confidence.")] = None,
    ambiguity_gap: Annotated[float | None, typer.Option("--ambiguity-gap", min=0.0, max=1.0, help="Minimum lead over the next detection label.")] = None,
    batch_size: Annotated[int | None, typer.Option("--batch-size", min=1, help="Detector inference batch size.")] = None,
):
    """Run managed stages in order, stopping at failures or the requested boundary."""
    try:
        result = run_pipeline(
            PipelineRunInput(
                session_id=session_id,
                recover=recover,
                next_only=next_only,
                until=until,
                mean_threshold=mean_threshold,
                std_threshold=std_threshold,
                high_level=high_level,
                pct_high_threshold=pct_high_threshold,
                burst_gap_threshold=burst_gap_threshold,
                similarity_threshold=similarity_threshold,
                model=model,
                confidence_threshold=confidence_threshold,
                ambiguity_gap=ambiguity_gap,
                batch_size=batch_size,
            )
        )
    except (PipelineRunError, SessionError, WorkspaceError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    stages = ", ".join(stage.process_name for stage in result.stages) or "none"
    logger.done(
        "Pipeline finished for %s: status=%s stages=%s%s",
        result.session_id,
        result.final_status,
        stages,
        f" stopped_at={result.stopped_at}" if result.stopped_at else "",
    )
    if any(stage.files_failed for stage in result.stages):
        raise typer.Exit(code=1)
