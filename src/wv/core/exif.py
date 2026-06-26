from pathlib import Path

import piexif
from PIL import Image, ExifTags

from wv.core.logging import get_logger

log = get_logger("Exif")


def read_exif(file_path: Path, metadata_tag: str) -> str | None:
    """
    Read a specific EXIF metadata from an image file.

    Args:
        file_path (Path): Path to the image file.
        metadata_tag (str): EXIF metadata tag to retrieve (e.g., "DateTime", "ImageDescription").

    Returns:
        str | None: The value of the specified EXIF metadata tag, or None if not found.
    """
    try:
        with Image.open(file_path) as image:
            exif_data = image._getexif()
            if not exif_data:
                log.warning(f"No EXIF data found in {file_path}")
                return None

            for tag_id, value in exif_data.items():
                decoded_tag = ExifTags.TAGS.get(tag_id)
                if decoded_tag == metadata_tag:
                    return value
    except Exception as e:
        log.error(f"Error reading EXIF data from {file_path}: {e}")
    return None


def write_exif_image_description(file_path: Path, data: str) -> None:
    """
    Write content into the ImageDescription EXIF metadata tag of an image file.

    Args:
        file_path (Path): Path to the image file.
        data (str): Description to write to the image's EXIF metadata.
    """
    try:
        img = Image.open(file_path)

        exif_bytes = img.info.get("exif")
        if exif_bytes:
            exif_dict = piexif.load(exif_bytes)
        else:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = data.encode("utf-8")

        exif_bytes = piexif.dump(exif_dict)
        img.save(file_path, exif=exif_bytes)

        log.info(f"Wrote ImageDescription to {file_path}")
    except Exception as e:
        log.error(f"Error writing EXIF data to {file_path}: {e}")
