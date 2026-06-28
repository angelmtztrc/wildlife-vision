import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from wv.core.files import ensure_directory, is_allowed_image_file


@dataclass(frozen=True)
class CleanCorruptedInput:
    source: Path
    output: Path
    dry_run: bool = False


@dataclass
class CleanCorruptedResult:
    files_discovered: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_corrupted: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _is_corrupted_image(file_path: Path) -> bool:
    try:
        with Image.open(file_path) as image:
            image.verify()

        with Image.open(file_path) as image:
            image.load()
    except Exception:
        return True

    return False


def run(input_data: CleanCorruptedInput) -> CleanCorruptedResult:
    destination = input_data.output / "ignored" / "corrupted"
    result = CleanCorruptedResult(destination=destination, dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    for file in input_data.source.iterdir():
        result.files_discovered += 1
        if not file.is_file() or not is_allowed_image_file(file):
            result.files_ignored += 1
            continue

        try:
            if not _is_corrupted_image(file):
                continue

            result.files_corrupted += 1

            if input_data.dry_run:
                continue

            destination.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file), destination / file.name)
            result.files_moved += 1
        except Exception:
            result.files_failed += 1

    return result
