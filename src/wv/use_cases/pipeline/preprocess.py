import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wv.use_cases.clean.bursts import CleanBurstsInput, CleanBurstsResult
from wv.use_cases.clean.bursts import run as run_clean_bursts
from wv.use_cases.clean.corrupted import CleanCorruptedInput, CleanCorruptedResult
from wv.use_cases.clean.corrupted import run as run_clean_corrupted
from wv.use_cases.clean.overexposed_ir import (
    CleanOverexposedIrInput,
    CleanOverexposedIrResult,
)
from wv.use_cases.clean.overexposed_ir import run as run_clean_overexposed_ir
from wv.use_cases.detect.content import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL,
    DetectContentInput,
    DetectContentResult,
)
from wv.use_cases.detect.content import run as run_detect_content
from wv.core.session import get_init_path

SESSION_NAME_PATTERN = re.compile(
    r"(?P<timestamp>\d{8}_\d{6})__(?P<camera>[A-Za-z0-9_]+)"
)


@dataclass(frozen=True)
class PipelinePreprocessInput:
    session_path: Path
    mean_threshold: float = 200.0
    std_threshold: float = 25.0
    high_level: int = 220
    ptc_high_threshold: float = 0.60
    burst_gap_threshold: int = 60
    similarity_threshold: int = 5
    model: str = DEFAULT_MODEL
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    batch_size: int = 32
    dry_run: bool = False


@dataclass
class PipelinePreprocessResult:
    session_path: Path
    init_path: Path
    corrupted_result: CleanCorruptedResult
    overexposed_result: CleanOverexposedIrResult
    bursts_result: CleanBurstsResult
    detect_result: DetectContentResult
    files_failed: int
    files_remaining_in_init: int
    dry_run: bool = False


def _validate_session_path(session_path: Path) -> None:
    if not session_path.exists():
        raise FileNotFoundError(session_path)

    if not session_path.is_dir():
        raise NotADirectoryError(session_path)

    match = SESSION_NAME_PATTERN.fullmatch(session_path.name)
    if match is None:
        raise ValueError(
            "session path must match YYYYMMDD_HHMMSS__CAMERA with a camera segment using only letters, numbers, and underscores"
        )

    try:
        datetime.strptime(match.group("timestamp"), "%Y%m%d_%H%M%S")
    except ValueError as exc:
        raise ValueError(
            "session path must contain a valid timestamp in YYYYMMDD_HHMMSS format"
        ) from exc


def run(input_data: PipelinePreprocessInput) -> PipelinePreprocessResult:
    _validate_session_path(input_data.session_path)

    init_path = get_init_path(input_data.session_path)
    if not init_path.exists():
        raise FileNotFoundError(f"expected init directory at {init_path}")

    if not init_path.is_dir():
        raise NotADirectoryError(f"expected init directory at {init_path}")

    corrupted_result = run_clean_corrupted(
        CleanCorruptedInput(
            source=init_path,
            output=input_data.session_path,
            dry_run=input_data.dry_run,
        )
    )
    overexposed_result = run_clean_overexposed_ir(
        CleanOverexposedIrInput(
            source=init_path,
            output=input_data.session_path,
            mean_threshold=input_data.mean_threshold,
            std_threshold=input_data.std_threshold,
            high_level=input_data.high_level,
            ptc_high_threshold=input_data.ptc_high_threshold,
            dry_run=input_data.dry_run,
        )
    )
    bursts_result = run_clean_bursts(
        CleanBurstsInput(
            source=init_path,
            output=input_data.session_path,
            burst_gap_threshold=input_data.burst_gap_threshold,
            similarity_threshold=input_data.similarity_threshold,
            dry_run=input_data.dry_run,
        )
    )
    detect_result = run_detect_content(
        DetectContentInput(
            source=init_path,
            output=input_data.session_path,
            model=input_data.model,
            confidence_threshold=input_data.confidence_threshold,
            batch_size=input_data.batch_size,
            dry_run=input_data.dry_run,
        )
    )

    files_remaining_in_init = len(list(init_path.iterdir()))
    files_failed = (
        corrupted_result.files_failed
        + overexposed_result.files_failed
        + bursts_result.files_failed
        + detect_result.files_failed
    )

    return PipelinePreprocessResult(
        session_path=input_data.session_path,
        init_path=init_path,
        corrupted_result=corrupted_result,
        overexposed_result=overexposed_result,
        bursts_result=bursts_result,
        detect_result=detect_result,
        files_failed=files_failed,
        files_remaining_in_init=files_remaining_in_init,
        dry_run=input_data.dry_run,
    )
