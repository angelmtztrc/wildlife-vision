from datetime import datetime
from pathlib import Path

from wv.core.exif import read_exif


def get_image_datetime(file_path: Path) -> datetime:
    """Return the image datetime from EXIF metadata or file modification time.

    Args:
        path: Path to the image file.

    Returns:
        The datetime read from the image EXIF metadata. If no supported EXIF
        datetime is available, returns the file's last modified datetime.
    """
    for metadata_tag in ("DateTimeOriginal", "DateTime"):
        value = read_exif(file_path, metadata_tag)
        if value:
            try:
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass

    return datetime.fromtimestamp(file_path.stat().st_mtime)
