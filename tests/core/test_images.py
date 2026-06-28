from datetime import datetime
from pathlib import Path

from wv.core.images import get_image_datetime


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
