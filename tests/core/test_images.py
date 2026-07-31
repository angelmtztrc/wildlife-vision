from datetime import datetime
from pathlib import Path

from wv.core.images import get_image_datetime, is_image_corrupted


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
