from dataclasses import dataclass
from pathlib import Path

from wv.core.bursts import (
    BurstCandidate,
    build_burst_reduction_plan,
    create_burst_candidate,
    validate_burst_thresholds,
)
from wv.core.display import display_file, display_path
from wv.core.files import (
    ensure_directory,
    get_content_digest,
    is_allowed_image_file,
    move_file_with_staged_copy,
)
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_bursts_path

logger = get_logger(__name__)

DEFAULT_BURST_GAP_THRESHOLD = 60
DEFAULT_SIMILARITY_THRESHOLD = 5


@dataclass(frozen=True)
class CleanBurstsInput:
    source: Path
    output: Path
    burst_gap_threshold: int = DEFAULT_BURST_GAP_THRESHOLD
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD
    dry_run: bool = False


@dataclass
class CleanBurstsResult:
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_bursts: int = 0
    files_reduced: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


def run(input_data: CleanBurstsInput) -> CleanBurstsResult:
    """Reduce similar images captured in rapid temporal bursts.

    The standalone operation analyzes only immediate supported image files in
    ``source`` and moves selected reductions to ``output/ignored/bursts``. It
    does not require or update a workspace database.

    Args:
        input_data: Source, output, thresholds, and dry-run configuration.

    Returns:
        Discovery, planning, movement, and failure counts for the operation.

    Raises:
        FileNotFoundError: If the source directory does not exist.
        NotADirectoryError: If the source path is not a directory.
        ValueError: If burst thresholds are outside the supported range.
    """
    validate_burst_thresholds(
        input_data.burst_gap_threshold, input_data.similarity_threshold
    )
    ensure_directory(input_data.source)

    destination = get_ignored_bursts_path(input_data.output)
    result = CleanBurstsResult(destination=destination, dry_run=input_data.dry_run)
    source_files = list(input_data.source.iterdir())
    result.files_discovered = len(source_files)
    candidates: list[BurstCandidate] = []

    logger.info(
        "Discovered %s entries for burst cleanup; destination is %s (burst_gap_threshold=%s, similarity_threshold=%s, dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.burst_gap_threshold,
        input_data.similarity_threshold,
        input_data.dry_run,
    )
    logger.info("Scanning burst cleanup candidates")

    with get_progress() as progress:
        scan_process = progress.add_task(
            "Scanning burst cleanup candidates", total=result.files_discovered
        )
        for file_path in source_files:
            if not file_path.is_file() or not is_allowed_image_file(file_path):
                result.files_ignored += 1
                logger.debug("Skipping %s: not a supported image file", display_file(file_path))
                progress.update(scan_process, advance=1)
                continue

            try:
                candidates.append(create_burst_candidate(str(file_path), file_path))
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to scan burst candidate %s", display_file(file_path))
            progress.update(scan_process, advance=1)

    plan = build_burst_reduction_plan(
        candidates,
        input_data.burst_gap_threshold,
        input_data.similarity_threshold,
    )
    result.files_processed = plan.processed
    result.files_bursts = plan.bursts
    result.files_failed += len(plan.failures)
    for failure in plan.failures:
        logger.error(
            "Failed to analyze burst image %s: %s",
            display_file(failure.path),
            failure.message,
        )

    logger.info(
        "Grouped %s scanned images into %s bursts", len(candidates), result.files_bursts
    )
    logger.info("Reducing burst sequences")

    with get_progress() as progress:
        reduction_process = progress.add_task(
            "Reducing burst sequences", total=len(plan.decisions)
        )
        for decision in plan.decisions:
            if decision.decision == "keep":
                result.files_ignored += 1
                progress.update(reduction_process, advance=1)
                continue

            result.files_reduced += 1
            destination_path = destination / decision.path.name
            if input_data.dry_run:
                logger.debug(
                    "Dry run: would move %s to %s",
                    display_file(decision.path),
                    display_file(destination_path),
                )
                progress.update(reduction_process, advance=1)
                continue

            try:
                if destination_path.exists():
                    raise FileExistsError(
                        f"Burst destination already exists: {destination_path}"
                    )
                source_digest = get_content_digest(decision.path)
                move_file_with_staged_copy(
                    decision.path,
                    destination_path,
                    verify=lambda staged_path: get_content_digest(staged_path)
                    == source_digest,
                )
                result.files_moved += 1
                logger.debug(
                    "Moved %s to %s",
                    display_file(decision.path),
                    display_file(destination_path),
                )
            except Exception:
                result.files_failed += 1
                logger.exception(
                    "Failed to move reduced burst image %s", display_file(decision.path)
                )
            progress.update(reduction_process, advance=1)

    return result
