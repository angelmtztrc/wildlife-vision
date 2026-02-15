import os
from pathlib import Path
from datetime import date, datetime

from wv.core.exif import read_exif
from wv.core.logging import get_logger


log = get_logger("Images")


def get_datetime_from_image(path: Path) -> datetime:
    """
    Get the date and time when the image was taken from its EXIF metadata. If the EXIF data is not available, fallback to the file's last modified time.

    Args:
        path (Path): Path to the image file.

    Returns:
        datetime: The date and time when the image was taken.
    """
    try:
        exif_datetime = read_exif(path, "DateTimeOriginal")
        if not exif_datetime:
            log.warning(f"No DateTimeOriginal EXIF data found in {path}")
            pass

        return datetime.strptime(exif_datetime, "%Y:%m:%d %H:%M:%S")

    except Exception as e:
        log.error(f"Error reading EXIF data from {path}: {e}")
        pass

    image_tm = os.path.getmtime(path)
    return date.fromtimestamp(image_tm)
