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
