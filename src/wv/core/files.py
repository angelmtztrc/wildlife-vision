import base64
import hashlib
from datetime import datetime
import re
import shutil
from pathlib import Path

allowed_image_exts = {".jpg", ".jpeg", ".png", ".heic"}


def is_allowed_image_file(file_path: Path) -> bool:
    """Return whether ``path`` has an allowed image file extension.

    Args:
        file_path: File path to validate.

    Returns:
        ``True`` if ``path`` has an extension listed in
        ``allowed_image_exts``. Otherwise, ``False``.
    """
    return file_path.suffix.lower() in allowed_image_exts


def ensure_directory(path: Path) -> None:
    """Ensure that ``path`` exists and is a directory.

    Args:
        path: Path to validate.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        NotADirectoryError: If ``path`` exists but is not a directory.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    if not path.is_dir():
        raise NotADirectoryError(path)


def get_file_id(file_path: Path) -> str:
    """Return a stable 6-character file ID derived from file content."""
    hasher = hashlib.blake2b(digest_size=20)

    with file_path.open("rb") as file_handle:
        while chunk := file_handle.read(8192):
            hasher.update(chunk)

    return base64.b32encode(hasher.digest()).decode("ascii")[:6]


def parse_ingested_image_filename(file_path: Path) -> dict[str, str] | None:
    """Parse filenames following ``YYYYMMDD_HHMMSS__SITE__ID``.

    Args:
        file_path: File path whose stem will be parsed.

    Returns:
        A dictionary with ``captured_at``, ``monitoring_site``, and ``file_id``
        when the stem matches the ingest naming convention. Otherwise, ``None``.
    """
    match = re.fullmatch(
        r"(?P<captured_at>\d{8}_\d{6})__(?P<monitoring_site>[^_][^_]*)__(?P<file_id>[^_][^_]*)",
        file_path.stem,
    )
    if match is None:
        return None

    parts = match.groupdict()

    try:
        datetime.strptime(parts["captured_at"], "%Y%m%d_%H%M%S")
    except ValueError:
        return None

    return parts


def copy_file_preserving_metadata(source: Path, destination: Path) -> Path:
    """Copy a file while preserving its contents and metadata when supported.

    This helper copies the file bytes unchanged, so embedded image metadata such
    as EXIF ``ImageDescription`` is preserved. Filesystem metadata is preserved
    on a best-effort basis via ``shutil.copy2()``, but creation time support is
    platform and filesystem dependent.

    Args:
        source: Existing file to copy.
        destination: Full destination file path.

    Returns:
        The destination path.

    Raises:
        FileNotFoundError: If ``source`` does not exist.
        IsADirectoryError: If ``source`` is not a file or ``destination`` is a directory.
        FileNotFoundError: If ``destination.parent`` does not exist.
        NotADirectoryError: If ``destination.parent`` exists but is not a directory.
        OSError: If the underlying copy operation fails.
    """
    if not source.exists():
        raise FileNotFoundError(source)

    if not source.is_file():
        raise IsADirectoryError(source)

    ensure_directory(destination.parent)

    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(destination)

    shutil.copy2(source, destination)

    return destination
