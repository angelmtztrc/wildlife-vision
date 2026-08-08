import shutil
from dataclasses import dataclass
from pathlib import Path

from wv.core.display import display_file, display_path
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.images import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PCT_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
    compute_image_exposure_metrics,
    is_image_overexposed,
    validate_exposure_thresholds,
)
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_overexposed_path

logger = get_logger(__name__)


@dataclass(frozen=True)
class CleanOverexposedIrInput:
    source: Path
    output: Path
    mean_threshold: float = DEFAULT_MEAN_THRESHOLD
    std_threshold: float = DEFAULT_STD_THRESHOLD
    high_level: int = DEFAULT_HIGH_LEVEL
    pct_high_threshold: float = DEFAULT_PCT_HIGH_THRESHOLD
    dry_run: bool = False


@dataclass
class CleanOverexposedIrResult:
    files_discovered: int = 0
    files_processed: int = 0
    files_moved: int = 0
    files_overexposed: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _validate_input(input_data: CleanOverexposedIrInput) -> None:
    validate_exposure_thresholds(
        input_data.mean_threshold,
        input_data.std_threshold,
        input_data.high_level,
        input_data.pct_high_threshold,
    )


def run(input_data: CleanOverexposedIrInput) -> CleanOverexposedIrResult:
    destination = get_ignored_overexposed_path(input_data.output)
    result = CleanOverexposedIrResult(
        destination=destination, dry_run=input_data.dry_run
    )

    _validate_input(input_data)

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())

    result.files_discovered = len(source_files)

    logger.info(
        "Discovered %s entries for overexposed IR cleanup; destination is %s (mean_threshold=%s, std_threshold=%s, high_level=%s, pct_high_threshold=%s, dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.mean_threshold,
        input_data.std_threshold,
        input_data.high_level,
        input_data.pct_high_threshold,
        input_data.dry_run,
    )
    logger.info("Processing overexposed IR candidates")

    with get_progress() as progress:
        process = progress.add_task(
            "Processing overexposed IR candidates", total=result.files_discovered
        )

        for file in source_files:
            if not file.is_file() or not is_allowed_image_file(file):
                result.files_ignored += 1

                logger.debug(
                    "Skipping %s: not a supported image file", display_file(file)
                )
                progress.update(process, advance=1)
                continue

            try:
                image_metrics = compute_image_exposure_metrics(
                    file_path=file, high_level=input_data.high_level
                )

                is_overexposed = is_image_overexposed(
                    image_metrics=image_metrics,
                    mean_threshold=input_data.mean_threshold,
                    std_threshold=input_data.std_threshold,
                    pct_high_threshold=input_data.pct_high_threshold,
                )
                result.files_processed += 1

                logger.debug(
                    "Classified %s: mean=%.2f std=%.2f pct_high=%.3f overexposed=%s",
                    display_file(file),
                    image_metrics.mean,
                    image_metrics.std,
                    image_metrics.pct_high,
                    is_overexposed,
                )

                if is_overexposed:
                    result.files_overexposed += 1

                    if input_data.dry_run:
                        logger.debug(
                            "Dry run: would move %s to %s",
                            display_file(file),
                            display_file(destination / file.name),
                        )
                        progress.update(process, advance=1)
                        continue

                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file), destination / file.name)
                    result.files_moved += 1

                    logger.debug(
                        "Moved %s to %s",
                        display_file(file),
                        display_file(destination / file.name),
                    )
                else:
                    result.files_ignored += 1
            except Exception:
                result.files_failed += 1
                logger.exception(
                    "Failed to process overexposed IR candidate %s",
                    display_file(file),
                )

            progress.update(process, advance=1)

    return result
