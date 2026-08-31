from pathlib import Path

import piexif
import pytest
from PIL import Image, ImageCms

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
    assert read_exif(image_path, "ImageDescription") == "scout camera"


def test_write_exif_image_description_preserves_jpeg_pixels_profile_and_exif(
    tmp_path: Path,
):
    image_path = tmp_path / "photo.jpg"
    image = Image.new("RGB", (3, 2))
    image.putdata(
        [
            (0, 0, 0),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 255),
            (128, 64, 32),
        ]
    )
    icc_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    exif_dict = {
        "0th": {piexif.ImageIFD.ImageDescription: b"original description"},
        "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2024:06:28 10:15:30"},
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    image.save(
        image_path,
        quality=100,
        exif=piexif.dump(exif_dict),
        icc_profile=icc_profile,
    )

    with Image.open(image_path) as saved_image:
        original_pixels = saved_image.tobytes()
        original_icc_profile = saved_image.info["icc_profile"]

    write_exif_image_description(image_path, "updated description")

    with Image.open(image_path) as updated_image:
        assert updated_image.tobytes() == original_pixels
        assert updated_image.info["icc_profile"] == original_icc_profile

    updated_exif = piexif.load(str(image_path))
    assert updated_exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2024:06:28 10:15:30"
    assert updated_exif["0th"][piexif.ImageIFD.ImageDescription] == b"updated description"


def test_write_exif_image_description_adds_exif_to_jpeg_without_existing_exif(
    make_image, tmp_path: Path
):
    image_path = make_image(tmp_path / "photo.jpg")

    write_exif_image_description(image_path, "scout camera")

    assert read_exif(image_path, "ImageDescription") == "scout camera"


@pytest.mark.parametrize("suffix", [".png", ".heic"])
def test_write_exif_image_description_rejects_unsupported_formats(
    suffix: str, tmp_path: Path
):
    image_path = tmp_path / f"photo{suffix}"
    image_path.write_bytes(b"original image bytes")
    original_bytes = image_path.read_bytes()

    with pytest.raises(ValueError, match="only for JPEG files"):
        write_exif_image_description(image_path, "scout camera")

    assert image_path.read_bytes() == original_bytes


def test_write_exif_image_description_raises_for_unreadable_file(
    make_corrupted_image, tmp_path: Path
):
    image_path = make_corrupted_image(tmp_path / "broken.jpg")

    with pytest.raises(Exception):
        write_exif_image_description(image_path, "scout camera")
