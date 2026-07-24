from dataclasses import dataclass
from pathlib import Path

from wv.core.display import display_file, display_path
from wv.core.exif import read_exif
from wv.core.files import copy_file_preserving_metadata, ensure_directory, is_allowed_image_file
from wv.core.logger import get_logger, get_progress
from wv.core.metadata import parse_image_description
from wv.core.session import get_detection_path

RESEARCH_GRADE_TRUE = "true"

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExportResearchGradeInput:
    session_path: Path
    output: Path | None = None
    dry_run: bool = False


@dataclass
class ExportResearchGradeResult:
    files_discovered: int = 0
    files_export_candidates: int = 0
    files_exported: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _animal_detection_directory(session_path: Path) -> Path:
    return get_detection_path(session_path, "animal")


def _default_output_directory(session_path: Path) -> Path:
    sessions_root = session_path.parent
    if sessions_root.name != "sessions":
        raise ValueError("session path must be located under a sessions directory")

    return sessions_root.parent / "export" / "research-grade"


def _read_research_grade(file_path: Path) -> bool:
    metadata = parse_image_description(read_exif(file_path, "ImageDescription"))
    value = metadata.get("Research_Grade")
    return value is not None and value.strip().lower() == RESEARCH_GRADE_TRUE


def run(input_data: ExportResearchGradeInput) -> ExportResearchGradeResult:
    ensure_directory(input_data.session_path)

    source_directory = _animal_detection_directory(input_data.session_path)
    ensure_directory(source_directory)

    destination = input_data.output or _default_output_directory(input_data.session_path)
    result = ExportResearchGradeResult(destination=destination, dry_run=input_data.dry_run)

    source_files = list(source_directory.iterdir())
    result.files_discovered = len(source_files)

    logger.info(
        "Discovered %s entries for research-grade export; destination is %s (dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.dry_run,
    )
    logger.info("Scanning research-grade export candidates")

    with get_progress() as progress:
        process = progress.add_task(
            "Scanning research-grade export candidates", total=result.files_discovered
        )

        for file_path in source_files:
            if not file_path.is_file() or not is_allowed_image_file(file_path):
                result.files_skipped += 1
                logger.debug(
                    "Skipping %s: not a supported image file", display_file(file_path)
                )
                progress.update(process, advance=1)
                continue

            if not _read_research_grade(file_path):
                result.files_skipped += 1
                logger.debug(
                    "Skipping %s: Research_Grade=true not present",
                    display_file(file_path),
                )
                progress.update(process, advance=1)
                continue

            result.files_export_candidates += 1
            destination_file = destination / file_path.name
            replaced_existing = destination_file.exists()

            if replaced_existing:
                result.files_replaced += 1

            if input_data.dry_run:
                logger.debug(
                    "Dry run: would export %s to %s",
                    display_file(file_path),
                    display_file(destination_file),
                )
                progress.update(process, advance=1)
                continue

            try:
                destination.mkdir(parents=True, exist_ok=True)
                copy_file_preserving_metadata(file_path, destination_file)
                result.files_exported += 1
                logger.debug(
                    "Exported %s to %s",
                    display_file(file_path),
                    display_file(destination_file),
                )
            except Exception:
                result.files_failed += 1
                logger.exception(
                    "Failed to export research-grade image %s",
                    display_file(file_path),
                )

            progress.update(process, advance=1)

    return result
