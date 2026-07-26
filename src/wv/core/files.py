import base64
import hashlib
import re
import shutil
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

allowed_image_exts = {".jpg", ".jpeg"}


def is_allowed_image_file(file_path: Path) -> bool:
    """Return whether a file path has a supported image extension.

    Args:
        file_path: File path to validate.

    Returns:
        ``True`` when the suffix, compared case-insensitively, is listed in
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


def get_content_digest(file_path: Path) -> str:
    """Return a stable Base32 BLAKE2b digest derived from file content.

    The digest is intended for durable persistence and duplicate
    investigation. It uses the same 20-byte BLAKE2b source digest as
    ``get_file_id()``, but returns the full Base32 value instead of the short
    filename prefix.

    Args:
        file_path: File whose bytes will be hashed.

    Returns:
        An uppercase Base32-encoded digest string.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    hasher = hashlib.blake2b(digest_size=20)

    with file_path.open("rb") as file_handle:
        while chunk := file_handle.read(8192):
            hasher.update(chunk)

    return base64.b32encode(hasher.digest()).decode("ascii")


def get_file_id(file_path: Path) -> str:
    """Return a stable six-character ID derived from file content.

    The ID is the first six Base32 characters of a 20-byte Blake2b digest. It
    is intended for concise ingest filenames, not as a collision-proof file
    identity.

    Args:
        file_path: File whose bytes will be hashed.

    Returns:
        An uppercase six-character Base32 identifier.

    Raises:
        OSError: If the file cannot be opened or read.
    """
    return get_content_digest(file_path)[:6]


def parse_ingested_image_filename(file_path: Path) -> dict[str, str] | None:
    """Parse filenames following ``YYYYMMDD_HHMMSS__SITE__ID``.

    Args:
        file_path: File path whose stem will be parsed.

    Returns:
        A dictionary with ``captured_at``, ``monitoring_site``, and ``file_id``
        when the stem matches the strict ingest naming convention. Otherwise,
        ``None``. The timestamp must be valid, the monitoring site must contain
        uppercase letters, digits, or underscores, and the file ID must be a
        six-character Base32 value.
    """
    match = re.fullmatch(
        r"(?P<captured_at>\d{8}_\d{6})__(?P<monitoring_site>[A-Z0-9_]+)__(?P<file_id>[A-Z2-7]{6})",
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


def move_file_with_staged_copy(
    source: Path,
    destination: Path,
    *,
    transform: Callable[[Path], None] | None = None,
    verify: Callable[[Path], bool] | None = None,
) -> tuple[bool, bool]:
    """Move a file by staging a verified copy before replacing the destination.

    The source is copied to a temporary file in the destination directory, then
    optionally transformed and verified. Only after those steps succeed is the
    temporary file atomically moved into place and the original source removed.
    If copying, transformation, verification, or replacement fails, the original
    source remains in place and the temporary file is removed when possible.

    Args:
        source: Existing file to move.
        destination: Full destination file path.
        transform: Optional callback used to mutate the staged temporary file
            before it is committed. The callback must raise on failure.
        verify: Optional callback used to validate the staged temporary file
            before it is committed. It must return ``True`` for success.

    Returns:
        A tuple ``(moved, replaced_existing)``. ``moved`` is always ``True`` if
        the function returns successfully. ``replaced_existing`` is ``True`` when
        a file already existed at ``destination`` before replacement.

    Raises:
        FileNotFoundError: If ``source`` does not exist.
        IsADirectoryError: If ``source`` is not a file or ``destination`` is a directory.
        NotADirectoryError: If ``destination.parent`` exists but is not a directory.
        ValueError: If ``verify`` returns ``False``.
        OSError: If copying, replacing, deleting, or temporary cleanup fails.

    Side Effects:
        Creates ``destination.parent`` when needed, writes a temporary file next
        to ``destination``, replaces ``destination``, and deletes ``source`` only
        after the replacement succeeds.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.parent.is_dir():
        raise NotADirectoryError(destination.parent)
    if destination.exists() and destination.is_dir():
        raise IsADirectoryError(destination)

    replaced_existing = destination.exists()
    temporary_destination = destination.with_name(
        f".{destination.stem}.{uuid4().hex}{destination.suffix}"
    )

    try:
        copy_file_preserving_metadata(source, temporary_destination)
        if transform is not None:
            transform(temporary_destination)
        if verify is not None and not verify(temporary_destination):
            raise ValueError(f"Staged file verification failed for: {source}")

        temporary_destination.replace(destination)
        source.unlink()
        return True, replaced_existing
    finally:
        if temporary_destination.exists():
            temporary_destination.unlink()
