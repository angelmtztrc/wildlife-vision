from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from wv.config import get_root_path
from wv.core.files import (
    copy_file_preserving_metadata,
    ensure_directory,
    get_file_id,
    is_allowed_image_file,
)
from wv.core.images import get_image_datetime


@dataclass(frozen=True)
class IngestSdInput:
    source: Path
    device: str
    monitoring_site: str
    mode: str
    dry_run: bool = False


@dataclass
class IngestSdResult:
    files_discovered: int = 0
    files_copied: int = 0
    files_deleted: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _verify_copy(source_file_id: str, copied_file: Path) -> bool:
    return get_file_id(copied_file) == source_file_id


def _replace_destination_with_verified_copy(
    source: Path, destination: Path, source_file_id: str
) -> tuple[bool, bool]:
    temp_destination = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    try:
        copy_file_preserving_metadata(source, temp_destination)

        if not _verify_copy(source_file_id, temp_destination):
            raise ValueError(f"Copied file verification failed for: {source}")

        replaced_existing = destination.exists()
        temp_destination.replace(destination)
        return True, replaced_existing
    finally:
        if temp_destination.exists():
            temp_destination.unlink()


def run(input_data: IngestSdInput) -> IngestSdResult:
    result = IngestSdResult(dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    root_path = get_root_path()
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = root_path / "sessions" / f"{session_timestamp}__{input_data.device}"
    egestion_path = session_dir / "initial"
    result.destination = egestion_path
    source_files = list(input_data.source.iterdir())

    for file in source_files:
        result.files_discovered += 1
        if not file.is_file() or not is_allowed_image_file(file):
            result.files_ignored += 1

            continue

        try:
            captured_at = get_image_datetime(file)
            captured_at_parsed = captured_at.strftime("%Y%m%d_%H%M%S")
            file_id = get_file_id(file)
            filename = (
                f"{captured_at_parsed}__{input_data.monitoring_site.upper()}__{file_id}"
                f"{file.suffix.lower()}"
            )
            destination = egestion_path / filename

            if input_data.dry_run:
                result.files_copied += 1
                if destination.exists():
                    result.files_replaced += 1
                if input_data.mode == "drain":
                    result.files_deleted += 1
                continue

            egestion_path.mkdir(parents=True, exist_ok=True)

            copied, replaced_existing = _replace_destination_with_verified_copy(
                source=file,
                destination=destination,
                source_file_id=file_id,
            )
            if copied:
                result.files_copied += 1
            if replaced_existing:
                result.files_replaced += 1

            if input_data.mode == "drain":
                file.unlink()
                result.files_deleted += 1
        except Exception:
            result.files_failed += 1

    return result
