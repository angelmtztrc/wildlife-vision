from datetime import datetime
from pathlib import Path

from wv.core.exif import read_exif


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
"""Image metadata helpers shared by ingest and cleanup workflows."""
