import os
import shutil
from pathlib import Path
from dataclasses import dataclass


allowed_image_exts = {".jpg", ".jpeg", ".png", ".heic"}


@dataclass
class ParsedFilename:
    datetime: str
    location: str
    detection: str | None


def copy_file(source_path: Path, destination_path: Path):
    """
    Copy a file from source_path to destination_path, preserving metadata.

    Args:
        source_path (Path): The path to the source file to be copied.
        destination_path (Path): The path to the destination where the file should be copied.
    """
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    tmp = destination_path.parent / (destination_path.name + ".tmpcopy")
    shutil.copy2(source_path, tmp)
    os.replace(tmp, destination_path)


def is_allowed_image_file(file: Path) -> bool:
    return file.suffix.lower() in allowed_image_exts


def parse_filename(file_path: Path):
    """
    Parse a filename into its components. The expected filename format is either:
    1) YYYYMMDD_HHMMSS__CAMERA_LOCATION
    2) YYYYMMDD_HHMMSS__CAMERA_LOCATION__DETECTION

    Args:
        file_path (Path): The path to the file whose name is to be parsed.

    Raises:
        ValueError: If the filename does not match the expected format.

    Returns:
        ParsedFilename: An object containing the parsed components of the filename.
    """
    file_path = Path(file_path)

    split = file_path.stem.split("__", maxsplit=2)

    if len(split) < 2:
        raise ValueError(
            f"Filename '{file_path.name}' does not match expected format 'YYYYMMDD_HHMMSS__CAMERA_LOCATION' or 'YYYYMMDD_HHMMSS__CAMERA_LOCATION__DETECTION'"
        )

    if len(split) == 2:
        return ParsedFilename(datetime=split[0], location=split[1], detection=None)

    return ParsedFilename(datetime=split[0], location=split[1], detection=split[2])
