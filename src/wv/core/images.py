from datetime import datetime
from pathlib import Path

from PIL import Image

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


def is_image_corrupted(file_path: Path) -> bool:
    """Return whether an image cannot be opened, verified, or fully decoded.

    Args:
        file_path: Image file to inspect.

    Returns:
        ``True`` when Pillow reports a file or decoding error while opening,
        verifying, or decoding the image. Otherwise, ``False``.

    Raises:
        Exception: Propagates unexpected errors so callers can report a failed
            inspection instead of treating an implementation error as image
            corruption.
    """
    try:
        with Image.open(file_path) as image:
            image.verify()

        with Image.open(file_path) as image:
            image.load()
    except (OSError, ValueError):
        return True

    return False
