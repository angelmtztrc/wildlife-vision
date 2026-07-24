from pathlib import Path

import piexif
from PIL import ExifTags, Image


def read_exif(file_path: Path, metadata_tag: str) -> str | None:
    """Read one EXIF metadata value from an image file.

    Args:
        file_path: Path to the image file.
        metadata_tag: EXIF tag name to retrieve, such as ``DateTime`` or
            ``ImageDescription``.

    Returns:
        The matching EXIF value, decoding byte values as UTF-8, or ``None`` if
        the tag is absent or the image cannot be read. Read failures are
        intentionally suppressed for best-effort metadata access.
    """
    try:
        with Image.open(file_path) as image:
            exif_data = image.getexif()
            if not exif_data:
                exif_data = None

            if exif_data:
                for tag_id, value in exif_data.items():
                    decoded_tag = ExifTags.TAGS.get(tag_id)
                    if decoded_tag == metadata_tag:
                        return value

            exif_bytes = image.info.get("exif")
            if not exif_bytes:
                return None

            exif_dict = piexif.load(exif_bytes)
            for ifd_name, ifd_data in exif_dict.items():
                if not isinstance(ifd_data, dict):
                    continue

                for tag_id, value in ifd_data.items():
                    tag_info = piexif.TAGS.get(ifd_name, {}).get(tag_id, {})
                    if tag_info.get("name") != metadata_tag:
                        continue

                    if isinstance(value, bytes):
                        return value.decode("utf-8", errors="ignore")

                    return value
    except Exception:
        # TODO: LOGGING
        pass
    return None


def write_exif_image_description(file_path: Path, data: str) -> None:
    """Write text to an image's EXIF ``ImageDescription`` tag in place.

    Args:
        file_path: Path to the image file.
        data: Description text to encode as UTF-8.

    Raises:
        OSError: If the image cannot be read or written.

    Notes:
        The image is re-saved at the same path with updated EXIF data.
    """
    with Image.open(file_path) as image:
        exif_bytes = image.info.get("exif")
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
        else:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = data.encode("utf-8")
        image.save(file_path, exif=piexif.dump(exif_dict))
"""Best-effort EXIF reading and writing helpers."""
