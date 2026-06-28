import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat

from wv.core.files import ensure_directory, is_allowed_image_file


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


def _compute_metrics(file: Path, high_level: int):
    with Image.open(file) as image:
        grayscale = image.convert("L")
        gs_stats = ImageStat.Stat(grayscale)
        mean = float(gs_stats.mean[0])
        std = float(gs_stats.stddev[0])

        gs_hist = grayscale.histogram()
        pixels_amount = sum(gs_hist)
        high_pixels = sum(gs_hist[high_level:]) if 0 <= high_level <= 255 else 0

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
    destination = input_data.output / "ignored" / "overexposed"
    result = CleanOverexposedIrResult(
        destination=destination, dry_run=input_data.dry_run
    )

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())

    result.files_discovered = len(source_files)

    for file in source_files:
        if not file.is_file() or not is_allowed_image_file(file):
            result.files_ignored += 1
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

            if is_overexposed:
                result.files_overexposed += 1

                if input_data.dry_run:
                    continue

                destination.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), destination / file.name)
                result.files_moved += 1
            else:
                result.files_ignored += 1
        except Exception:
            result.files_failed += 1

    return result
