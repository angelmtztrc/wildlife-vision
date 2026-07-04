from pathlib import Path


def display_file(path: Path) -> str:
    return path.name or path.as_posix()


def display_path(path: Path, *, max_parts: int = 3) -> str:
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
