from datetime import datetime
from pathlib import Path

import pytest

from wv.core.images import (
    compute_image_exposure_metrics,
    get_image_datetime,
    is_image_corrupted,
    is_image_overexposed,
    validate_exposure_thresholds,
)


def test_get_image_datetime_prefers_datetime_original(
    make_image,
    set_mtime,
    tmp_path: Path,
):
    image_path = make_image(
        tmp_path / "photo.jpg",
        exif={
            "DateTime": "2023:01:02 03:04:05",
            "DateTimeOriginal": "2024:06:28 10:15:30",
        },
    )
    set_mtime(image_path, datetime(2022, 1, 1, 0, 0, 0))

    assert get_image_datetime(image_path) == datetime(2024, 6, 28, 10, 15, 30)


def test_get_image_datetime_falls_back_to_datetime_tag(
    make_image,
    set_mtime,
    tmp_path: Path,
):
    image_path = make_image(
        tmp_path / "photo.jpg",
        exif={"DateTime": "2024:06:28 10:15:30"},
    )
    set_mtime(image_path, datetime(2022, 1, 1, 0, 0, 0))

    assert get_image_datetime(image_path) == datetime(2024, 6, 28, 10, 15, 30)


def test_get_image_datetime_falls_back_to_mtime_when_exif_missing(
    make_image,
    set_mtime,
    tmp_path: Path,
):
    image_path = make_image(tmp_path / "photo.jpg")
    modified_at = datetime(2021, 5, 6, 7, 8, 9)
    set_mtime(image_path, modified_at)

    assert get_image_datetime(image_path) == modified_at


def test_get_image_datetime_falls_back_to_mtime_when_exif_is_invalid(
    make_image,
    set_mtime,
    tmp_path: Path,
):
    image_path = make_image(
        tmp_path / "photo.jpg",
        exif={"DateTimeOriginal": "invalid-datetime"},
    )
    modified_at = datetime(2021, 5, 6, 7, 8, 9)
    set_mtime(image_path, modified_at)

    assert get_image_datetime(image_path) == modified_at


def test_is_image_corrupted_returns_false_for_decodable_image(make_image, tmp_path: Path):
    image_path = make_image(tmp_path / "photo.jpg")

    assert is_image_corrupted(image_path) is False


def test_is_image_corrupted_returns_true_for_invalid_image(
    make_corrupted_image, tmp_path: Path
):
    image_path = make_corrupted_image(tmp_path / "broken.jpg")

    assert is_image_corrupted(image_path) is True


def test_compute_image_exposure_metrics_and_classification(make_image, tmp_path: Path):
    image_path = make_image(tmp_path / "white.jpg", color=(255, 255, 255))

    metrics = compute_image_exposure_metrics(image_path, high_level=220)

    assert metrics.mean == 255.0
    assert metrics.std == 0.0
    assert metrics.ptc_high == 1.0
    assert is_image_overexposed(
        metrics,
        mean_threshold=200.0,
        std_threshold=25.0,
        ptc_high_threshold=0.6,
    )


@pytest.mark.parametrize(
    ("mean_threshold", "std_threshold", "high_level", "ptc_high_threshold"),
    [
        (-1.0, 25.0, 220, 0.6),
        (200.0, -1.0, 220, 0.6),
        (200.0, 25.0, 256, 0.6),
        (200.0, 25.0, 220, 1.1),
        (200.0, float("nan"), 220, 0.6),
    ],
)
def test_validate_exposure_thresholds_rejects_invalid_values(
    mean_threshold: float,
    std_threshold: float,
    high_level: int,
    ptc_high_threshold: float,
):
    with pytest.raises(ValueError):
        validate_exposure_thresholds(
            mean_threshold,
            std_threshold,
            high_level,
            ptc_high_threshold,
        )
