from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from wv.core.display import display_file, display_path
from wv.core.files import copy_file_preserving_metadata, ensure_directory, get_file_id, is_allowed_image_file
from wv.core.images import get_image_datetime
from wv.core.logger import get_logger, get_progress
from wv.core.session import get_init_path, require_session_component
from wv.persistence.repositories import DeviceRepository, MonitoringSiteRepository
from wv.persistence.session import session_scope
from wv.workspace.workspace_config import require_workspace_database_path, require_workspace_path

logger = get_logger(__name__)


@dataclass(frozen=True)
class IngestInput:
    source: Path
    device_id: str
    monitoring_site_id: str
    mode: str
    dry_run: bool = False


@dataclass
class IngestResult:
    files_discovered: int = 0
    files_copied: int = 0
    files_deleted: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _validate_ingest_identity(
    session: Session, device_id: str, monitoring_site_id: str
) -> None:
    DeviceRepository(session).get(device_id)
    MonitoringSiteRepository(session).get(monitoring_site_id)


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


def _get_session_path(workspace_path: Path, device_id: str, dry_run: bool) -> Path:
    timestamp = datetime.now()

    while True:
        session_path = workspace_path / "sessions" / (
            f"{timestamp.strftime('%Y%m%d_%H%M%S')}__{device_id}"
        )
        if dry_run:
            if not session_path.exists():
                return session_path
        else:
            try:
                session_path.mkdir(parents=True)
                return session_path
            except FileExistsError:
                pass

        timestamp += timedelta(seconds=1)


def run(input_data: IngestInput) -> IngestResult:
    if input_data.mode not in {"drain", "copy"}:
        raise ValueError(f"Unknown ingest mode: {input_data.mode}")

    workspace_path = require_workspace_path()
    with session_scope(require_workspace_database_path(workspace_path)) as session:
        _validate_ingest_identity(
            session, input_data.device_id, input_data.monitoring_site_id
        )

    ensure_directory(input_data.source)
    device_id = require_session_component(input_data.device_id, "Device ID")
    monitoring_site_id = require_session_component(
        input_data.monitoring_site_id, "Monitoring site ID"
    )

    result = IngestResult(dry_run=input_data.dry_run)
    session_path = _get_session_path(workspace_path, device_id, input_data.dry_run)
    destination_path = get_init_path(session_path)
    if not input_data.dry_run:
        destination_path.mkdir(exist_ok=True)
    source_files = [file for file in input_data.source.iterdir() if file.name != ".wv"]

    result.destination = destination_path
    result.files_discovered = len(source_files)

    logger.info(
        "Discovered %s entries; destination session path is %s",
        result.files_discovered,
        display_path(destination_path),
    )
    logger.info("Processing source files")

    with get_progress() as progress:
        process = progress.add_task("Processing source files", total=result.files_discovered)

        for file in source_files:
            if not file.is_file() or not is_allowed_image_file(file):
                result.files_ignored += 1
                logger.debug("Skipping %s: not a supported image file", display_file(file))
                progress.update(process, advance=1)
                continue

            try:
                captured_at = get_image_datetime(file)
                captured_at_parsed = captured_at.strftime("%Y%m%d_%H%M%S")
                file_id = get_file_id(file)
                filename = (
                    f"{captured_at_parsed}__{monitoring_site_id.upper()}__{file_id}"
                    f"{file.suffix.lower()}"
                )
                destination = destination_path / filename

                logger.debug(
                    "Prepared ingest for %s: captured_at=%s, file_id=%s, destination=%s",
                    display_file(file),
                    captured_at_parsed,
                    file_id,
                    display_file(destination),
                )

                if input_data.dry_run:
                    result.files_copied += 1
                    if destination.exists():
                        result.files_replaced += 1
                    if input_data.mode == "drain":
                        result.files_deleted += 1
                    logger.debug(
                        "Dry run: would copy %s to %s%s%s",
                        display_file(file),
                        display_file(destination),
                        " and replace existing file" if destination.exists() else "",
                        " and delete source" if input_data.mode == "drain" else "",
                    )
                    progress.update(process, advance=1)
                    continue

                copied, replaced_existing = _replace_destination_with_verified_copy(
                    source=file,
                    destination=destination,
                    source_file_id=file_id,
                )

                if copied:
                    result.files_copied += 1
                    logger.debug("Copied %s to %s", display_file(file), display_file(destination))
                if replaced_existing:
                    result.files_replaced += 1
                    logger.debug(
                        "Replaced existing destination file at %s", display_file(destination)
                    )

                if input_data.mode == "drain":
                    file.unlink()
                    result.files_deleted += 1
                    logger.debug("Deleted source file after ingest: %s", display_file(file))

                progress.update(process, advance=1)
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to ingest %s", file)
                progress.update(process, advance=1)

    return result
