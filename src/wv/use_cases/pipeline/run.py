import json
from dataclasses import dataclass, field

from wv.core.logger import get_logger
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedInput
from wv.use_cases.session.clean_corrupted import run as run_clean_corrupted
from wv.use_cases.session.clean_overexposed_ir import SessionCleanOverexposedIrInput
from wv.use_cases.session.clean_overexposed_ir import run as run_clean_overexposed_ir
from wv.use_cases.session.detect_content import SessionDetectContentInput
from wv.use_cases.session.detect_content import run as run_detect_content
from wv.use_cases.session.status import SessionStageStatus, SessionStatusInput
from wv.use_cases.session.status import run as run_session_status
from wv.use_cases.session._shared import PROCESS_NAMES, resolve_managed_session, session_workflow_lock
from wv.workspace.workspace_config import load_processing_config

PROCESS_ALIASES = dict(
    zip(
        ("corrupted", "overexposed-ir", "detect-content"),
        PROCESS_NAMES,
        strict=True,
    )
)

logger = get_logger(__name__)


class PipelineRunError(ValueError):
    pass


@dataclass(frozen=True)
class PipelineRunInput:
    session_id: str
    recover: bool = False
    next_only: bool = False
    until: str | None = None
    mean_threshold: float | None = None
    std_threshold: float | None = None
    high_level: int | None = None
    pct_high_threshold: float | None = None
    model: str | None = None
    speciesnet_model: str | None = None
    batch_size: int | None = None


@dataclass(frozen=True)
class PipelineStageResult:
    process_name: str
    status: str
    files_failed: int


@dataclass(frozen=True)
class PipelineRunResult:
    session_id: str
    stages: list[PipelineStageResult] = field(default_factory=list)
    final_status: str = "completed"
    stopped_at: str | None = None


def _until_process(until: str | None) -> str | None:
    if until is None:
        return None
    try:
        return PROCESS_ALIASES[until]
    except KeyError as exc:
        expected = ", ".join(PROCESS_ALIASES)
        raise PipelineRunError(f"Unknown pipeline stage: {until}. Expected one of: {expected}.") from exc


def _stage(status, process_name: str) -> SessionStageStatus:
    return next(stage for stage in status.stages if stage.name == process_name)


def _parameters(stage: SessionStageStatus) -> dict[str, object]:
    if stage.parameters_json is None:
        return {}
    try:
        value = json.loads(stage.parameters_json)
    except json.JSONDecodeError as exc:
        raise PipelineRunError(
            f"Session process has invalid recorded parameters: {stage.name}"
        ) from exc
    if not isinstance(value, dict):
        raise PipelineRunError(f"Session process has invalid recorded parameters: {stage.name}")
    return value


def _value(
    *, provided: object | None, stored: dict[str, object], key: str, default: object
) -> object:
    if key in stored:
        if provided is not None and provided != stored[key]:
            raise PipelineRunError(
                f"Pipeline retry must use the recorded parameter {key}: {stored[key]!r}."
            )
        return stored[key]
    return default if provided is None else provided


def _run_stage(input_data: PipelineRunInput, process_name: str, stage: SessionStageStatus, settings):
    stored = _parameters(stage)
    recover = input_data.recover if stage.status == "in_progress" else False
    if process_name == "clean_corrupted":
        return run_clean_corrupted(
            SessionCleanCorruptedInput(session_id=input_data.session_id, recover=recover)
        )
    if process_name == "clean_overexposed_ir":
        return run_clean_overexposed_ir(
            SessionCleanOverexposedIrInput(
                session_id=input_data.session_id,
                mean_threshold=float(_value(provided=input_data.mean_threshold, stored=stored, key="mean_threshold", default=settings.overexposed_ir.mean_threshold)),
                std_threshold=float(_value(provided=input_data.std_threshold, stored=stored, key="std_threshold", default=settings.overexposed_ir.std_threshold)),
                high_level=int(_value(provided=input_data.high_level, stored=stored, key="high_level", default=settings.overexposed_ir.high_level)),
                pct_high_threshold=float(_value(provided=input_data.pct_high_threshold, stored=stored, key="pct_high_threshold", default=settings.overexposed_ir.pct_high_threshold)),
                recover=recover,
            )
        )
    if process_name == "detect_content":
        return run_detect_content(
            SessionDetectContentInput(
                session_id=input_data.session_id,
                model=str(_value(provided=input_data.model, stored=stored, key="model", default=settings.detection.model)),
                speciesnet_model=str(_value(provided=input_data.speciesnet_model, stored=stored, key="speciesnet_model", default=settings.detection.speciesnet_model)),
                batch_size=(
                    int(
                        _value(
                            provided=input_data.batch_size,
                            stored=stored,
                            key="batch_size",
                            default=settings.detection.batch_size,
                        )
                    )
                    if input_data.batch_size is not None or "batch_size" in stored
                    else None
                ),
                recover=recover,
            )
        )
    raise PipelineRunError(f"Unknown session process: {process_name}")


def run(input_data: PipelineRunInput) -> PipelineRunResult:
    if input_data.next_only and input_data.until is not None:
        raise PipelineRunError("--next and --until cannot be used together.")
    until_process = _until_process(input_data.until)
    managed_session = resolve_managed_session(input_data.session_id)
    settings = load_processing_config()
    stages: list[PipelineStageResult] = []

    with session_workflow_lock(managed_session.session_path):
        while True:
            status = run_session_status(SessionStatusInput(session_id=input_data.session_id))
            if status.overall_status == "completed":
                return PipelineRunResult(input_data.session_id, stages, "completed")

            if status.next_process is None or status.next_action is None:
                raise PipelineRunError(
                    f"Pipeline cannot continue: {status.overall_status}."
                )
            process_name = status.next_process
            process_index = PROCESS_NAMES.index(process_name)
            if until_process is not None and process_index > PROCESS_NAMES.index(until_process):
                return PipelineRunResult(
                    input_data.session_id,
                    stages,
                    "stopped",
                    stopped_at=until_process,
                )
            if status.next_action == "recover" and not input_data.recover:
                raise PipelineRunError(
                    f"Pipeline recovery is required for {process_name}. Use --recover after confirming the prior command stopped."
                )
            if status.next_action not in {"run", "retry", "recover"}:
                raise PipelineRunError(f"Pipeline cannot perform action: {status.next_action}")

            logger.info("Running pipeline stage %s for session %s", process_name, input_data.session_id)
            result = _run_stage(input_data, process_name, _stage(status, process_name), settings)
            stage_result = PipelineStageResult(
                process_name=process_name,
                status=result.process.status if result.process is not None else "completed",
                files_failed=result.files_failed,
            )
            stages.append(stage_result)
            if result.files_failed:
                return PipelineRunResult(
                    input_data.session_id,
                    stages,
                    "completed_with_failures",
                    stopped_at=process_name,
                )
            if input_data.next_only or process_name == until_process:
                return PipelineRunResult(
                    input_data.session_id,
                    stages,
                    "completed" if process_name == PROCESS_NAMES[-1] else "stopped",
                    stopped_at=process_name,
                )
