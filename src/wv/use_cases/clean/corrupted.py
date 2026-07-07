import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from wv.core.display import display_file, display_path
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.logger import get_logger, get_progress

logger = get_logger(__name__)


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

    source_files = list(input_data.source.iterdir())

    result.files_discovered = len(source_files)

    logger.info(
        "Discovered %s entries for corrupted image cleanup; destination is %s (dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.dry_run,
    )

    with get_progress() as progress:
        process = progress.add_task(
            "Processing corrupted image candidates", total=result.files_discovered
        )

        for file in source_files:
            if not file.is_file() or not is_allowed_image_file(file):
                result.files_ignored += 1
                logger.debug(
                    "Skipping %s: not a supported image file", display_file(file)
                )
                progress.update(process, advance=1)
                continue

            try:
                if not _is_corrupted_image(file):
                    logger.debug("Keeping %s: image is readable", display_file(file))
                    progress.update(process, advance=1)
                    continue

                result.files_corrupted += 1
                logger.debug("Detected corrupted image %s", display_file(file))

                if input_data.dry_run:
                    logger.debug(
                        "Dry run: would move %s to %s",
                        display_file(file),
                        display_file(destination / file.name),
                    )
                    progress.update(process, advance=1)
                    continue

                destination.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file), destination / file.name)
                result.files_moved += 1
                logger.debug(
                    "Moved %s to %s",
                    display_file(file),
                    display_file(destination / file.name),
                )
            except Exception:
                result.files_failed += 1
                logger.exception(
                    "Failed to process corrupted image candidate %s",
                    display_file(file),
                )

            progress.update(process, advance=1)

    return result
