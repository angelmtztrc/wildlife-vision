from pathlib import Path

from wv.core.exif import read_exif, write_exif_image_description


def test_read_exif_returns_requested_tag(make_image, tmp_path: Path):
    image_path = make_image(
        tmp_path / "photo.jpg",
        exif={"DateTimeOriginal": "2024:06:28 10:15:30"},
    )

    assert read_exif(image_path, "DateTimeOriginal") == "2024:06:28 10:15:30"


def test_read_exif_returns_none_for_missing_tag(make_image, tmp_path: Path):
    image_path = make_image(tmp_path / "photo.jpg")

    assert read_exif(image_path, "DateTimeOriginal") is None


def test_read_exif_returns_none_for_unreadable_file(
    make_corrupted_image, tmp_path: Path
):
    image_path = make_corrupted_image(tmp_path / "broken.jpg")

    assert read_exif(image_path, "DateTimeOriginal") is None


def test_write_exif_image_description_updates_image(make_image, tmp_path: Path):
    image_path = make_image(tmp_path / "photo.jpg")

    write_exif_image_description(image_path, "scout camera")
    value = read_exif(image_path, "ImageDescription")

    if isinstance(value, bytes):
        assert value.decode("utf-8") == "scout camera"
    else:
        assert value == "scout camera"
