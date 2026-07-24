from pathlib import Path


def display_file(path: Path) -> str:
    """Return the most concise display name for a file path.

    Args:
        path: Path to format for display only.

    Returns:
        The final path component when present; otherwise, the POSIX path text.
    """
    return path.name or path.as_posix()


def display_path(path: Path, *, max_parts: int = 3) -> str:
    """Return a concise, display-only representation of a path.

    Args:
        path: Path to format for logs or status messages.
        max_parts: Maximum trailing components to retain when an absolute path
            is outside the current working directory.

    Returns:
        The original POSIX text for relative paths, a current-working-directory
        relative path when possible, or a truncated absolute path prefixed with
        ``.../`` when it exceeds ``max_parts`` components.
    """
    if not path.is_absolute():
        return path.as_posix()

    cwd = Path.cwd()

    try:
        relative_path = path.relative_to(cwd)
    except ValueError:
        relative_path = None

    if relative_path is not None:
        return relative_path.as_posix()

    parts = path.parts[1:] if path.anchor else path.parts
    if len(parts) <= max_parts:
        return path.as_posix()

    return f".../{'/'.join(parts[-max_parts:])}"
"""Path formatting helpers for concise user-facing log output."""
