from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path

from PIL import Image

from wv.core.exif import read_exif

DEFAULT_MEAN_THRESHOLD = 200.0
DEFAULT_STD_THRESHOLD = 25.0
DEFAULT_HIGH_LEVEL = 220
DEFAULT_PTC_HIGH_THRESHOLD = 0.60


@dataclass(frozen=True)
class ImageExposureMetrics:
    """Grayscale brightness metrics used for overexposure classification."""

    mean: float
    std: float
    ptc_high: float


def get_image_datetime(file_path: Path) -> datetime:
    """Return an image capture datetime from EXIF metadata or modification time.

    Args:
        file_path: Path to the image file.

    Returns:
        A naive datetime from ``DateTimeOriginal`` first, then ``DateTime``.
        If neither contains a valid ``YYYY:MM:DD HH:MM:SS`` value, returns the
        local datetime represented by the file's modification timestamp.

    Raises:
        OSError: If the modification time cannot be read after EXIF fallback.
    """
    for metadata_tag in ("DateTimeOriginal", "DateTime"):
        value = read_exif(file_path, metadata_tag)
        if value:
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass

    return datetime.fromtimestamp(file_path.stat().st_mtime)


def is_image_corrupted(file_path: Path) -> bool:
    """Return whether an image cannot be opened, verified, or fully decoded.

    Args:
        file_path: Image file to inspect.

    Returns:
        ``True`` when Pillow reports a file or decoding error while opening,
        verifying, or decoding the image. Otherwise, ``False``.

    Raises:
        Exception: Propagates unexpected errors so callers can report a failed
            inspection instead of treating an implementation error as image
            corruption.
    """
    try:
        with Image.open(file_path) as image:
            image.verify()

        with Image.open(file_path) as image:
            image.load()
    except (OSError, ValueError):
        return True

    return False


def validate_exposure_thresholds(
    mean_threshold: float,
    std_threshold: float,
    high_level: int,
    ptc_high_threshold: float,
) -> None:
    """Validate values used for grayscale overexposure classification.

    Args:
        mean_threshold: Minimum grayscale mean for bright, uniform images.
        std_threshold: Maximum grayscale standard deviation for uniform images.
        high_level: Inclusive grayscale cutoff for near-white histogram pixels.
        ptc_high_threshold: Minimum near-white pixel fraction.

    Raises:
        ValueError: If any threshold is outside the supported grayscale or
            fractional range.
    """
    if not isfinite(mean_threshold) or not 0.0 <= mean_threshold <= 255.0:
        raise ValueError("mean_threshold must be between 0.0 and 255.0")
    if not isfinite(std_threshold) or std_threshold < 0.0:
        raise ValueError("std_threshold must be greater than or equal to 0.0")
    if not 0 <= high_level <= 255:
        raise ValueError("high_level must be between 0 and 255")
    if not isfinite(ptc_high_threshold) or not 0.0 <= ptc_high_threshold <= 1.0:
        raise ValueError("ptc_high_threshold must be between 0.0 and 1.0")


def compute_image_exposure_metrics(
    file_path: Path, high_level: int
) -> ImageExposureMetrics:
    """Compute grayscale brightness metrics for an image.

    Args:
        file_path: Image file to decode and measure.
        high_level: Inclusive grayscale cutoff for near-white pixels.

    Returns:
        Mean grayscale brightness, grayscale standard deviation, and the
        fraction of pixels at or above ``high_level``.

    Raises:
        OSError: If Pillow cannot open or decode the image.
        ValueError: If ``high_level`` is outside the supported grayscale range.
    """
    if not 0 <= high_level <= 255:
        raise ValueError("high_level must be between 0 and 255")

    from PIL import Image, ImageStat

    with Image.open(file_path) as image:
        grayscale = image.convert("L")
        grayscale_stats = ImageStat.Stat(grayscale)
        mean = float(grayscale_stats.mean[0])
        std = float(grayscale_stats.stddev[0])

        grayscale_histogram = grayscale.histogram()
        pixels_amount = sum(grayscale_histogram)
        high_pixels = sum(grayscale_histogram[high_level:])
        ptc_high = (high_pixels / pixels_amount) if pixels_amount > 0 else 0.0

    return ImageExposureMetrics(mean=mean, std=std, ptc_high=ptc_high)


def is_image_overexposed(
    image_metrics: ImageExposureMetrics,
    mean_threshold: float,
    std_threshold: float,
    ptc_high_threshold: float,
) -> bool:
    """Return whether exposure metrics meet either overexposure condition.

    Args:
        image_metrics: Grayscale metrics calculated for an image.
        mean_threshold: Minimum mean for a bright, uniform image.
        std_threshold: Maximum standard deviation for a uniform image.
        ptc_high_threshold: Minimum fraction of near-white pixels.

    Returns:
        ``True`` when the image is bright and uniform, or has sufficient
        near-white pixels. Otherwise, ``False``.
    """
    is_bright_and_uniform = (
        image_metrics.mean >= mean_threshold and image_metrics.std <= std_threshold
    )
    has_many_near_white_pixels = image_metrics.ptc_high >= ptc_high_threshold
    return is_bright_and_uniform or has_many_near_white_pixels
