import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat

from wv.core.display import display_file, display_path
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_ignored_overexposed_path

logger = get_logger(__name__)


@dataclass(frozen=True)
class CleanOverexposedIrInput:
    source: Path
    output: Path
    mean_threshold: float
    std_threshold: float
    high_level: int
    ptc_high_threshold: float
    dry_run: bool = False


@dataclass
class CleanOverexposedIrResult:
    files_discovered: int = 0
    files_moved: int = 0
    files_overexposed: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass
class ImageMetrics:
    mean: float
    std: float
    ptc_high: float


def _validate_input(input_data: CleanOverexposedIrInput) -> None:
    if not 0.0 <= input_data.mean_threshold <= 255.0:
        raise ValueError("mean_threshold must be between 0.0 and 255.0")
    if input_data.std_threshold < 0.0:
        raise ValueError("std_threshold must be greater than or equal to 0.0")
    if not 0 <= input_data.high_level <= 255:
        raise ValueError("high_level must be between 0 and 255")
    if not 0.0 <= input_data.ptc_high_threshold <= 1.0:
        raise ValueError("ptc_high_threshold must be between 0.0 and 1.0")


def _compute_metrics(file: Path, high_level: int):
    with Image.open(file) as image:
        grayscale = image.convert("L")
        gs_stats = ImageStat.Stat(grayscale)
        mean = float(gs_stats.mean[0])
        std = float(gs_stats.stddev[0])

        gs_hist = grayscale.histogram()
        pixels_amount = sum(gs_hist)
        high_pixels = sum(gs_hist[high_level:])

        ptc_high = (high_pixels / pixels_amount) if pixels_amount > 0 else 0.0

    return ImageMetrics(mean=mean, std=std, ptc_high=ptc_high)


def _is_overexposed(
    image_metrics: ImageMetrics,
    mean_threshold: float,
    std_threshold: float,
    ptc_high_threshold: float,
):
    is_bright_and_uniform = (
        image_metrics.mean >= mean_threshold and image_metrics.std <= std_threshold
    )

    has_many_near_white_pixels = image_metrics.ptc_high >= ptc_high_threshold

    return is_bright_and_uniform or has_many_near_white_pixels


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
        "Discovered %s entries for overexposed IR cleanup; destination is %s (mean_threshold=%s, std_threshold=%s, high_level=%s, ptc_high_threshold=%s, dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.mean_threshold,
        input_data.std_threshold,
        input_data.high_level,
        input_data.ptc_high_threshold,
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
                image_metrics = _compute_metrics(
                    file=file, high_level=input_data.high_level
                )

                is_overexposed = _is_overexposed(
                    image_metrics=image_metrics,
                    mean_threshold=input_data.mean_threshold,
                    std_threshold=input_data.std_threshold,
                    ptc_high_threshold=input_data.ptc_high_threshold,
                )

                logger.debug(
                    "Classified %s: mean=%.2f std=%.2f ptc_high=%.3f overexposed=%s",
                    display_file(file),
                    image_metrics.mean,
                    image_metrics.std,
                    image_metrics.ptc_high,
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
