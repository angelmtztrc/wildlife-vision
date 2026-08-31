from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from wv.core.display import display_file, display_path
from wv.core.files import (
    copy_file_preserving_metadata,
    get_content_digest,
    is_allowed_image_file,
)
from wv.core.logger import get_logger, get_progress
from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExportFavoritesInput:
    session_id: str
    output: Path | None = None
    dry_run: bool = False


@dataclass
class ExportFavoritesResult:
    files_discovered: int = 0
    files_export_candidates: int = 0
    files_exported: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    destination: Path = Path()
    dry_run: bool = False


def run(input_data: ExportFavoritesInput) -> ExportFavoritesResult:
    """Copy favorited animal images from the managed session inventory."""
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    with sql_session_scope(managed_session.database_path) as sql_session:
        images = SessionImageRepository(sql_session).list_for_session_state(
            managed_session.session.id,
            "detection/animal",
            favorites_only=True,
        )

    destination = input_data.output or (
        managed_session.session_path.parent.parent
        / "exports"
        / managed_session.session.id
        / "favorites"
    )
    result = ExportFavoritesResult(destination=destination, dry_run=input_data.dry_run)
    result.files_discovered = len(images)

    logger.info(
        "Discovered %s favorite images for export; destination is %s (dry_run=%s)",
        result.files_discovered,
        display_path(destination),
        input_data.dry_run,
    )

    with get_progress() as progress:
        process = progress.add_task("Exporting favorite images", total=result.files_discovered)
        for image in images:
            file_path = shared._resolve_session_path(
                managed_session.session_path, image.current_relative_path
            )
            if not file_path.is_file() or not is_allowed_image_file(file_path):
                result.files_skipped += 1
                logger.debug(
                    "Skipping %s: missing or unsupported inventory file", display_file(file_path)
                )
                progress.update(process, advance=1)
                continue
            if (
                file_path.stat().st_size != image.content_size_bytes
                or get_content_digest(file_path) != image.content_digest
            ):
                result.files_failed += 1
                logger.error("Inventory content changed for %s", display_file(file_path))
                progress.update(process, advance=1)
                continue

            result.files_export_candidates += 1
            destination_file = destination / file_path.name
            if destination_file.exists():
                result.files_replaced += 1
            if input_data.dry_run:
                progress.update(process, advance=1)
                continue

            try:
                destination.mkdir(parents=True, exist_ok=True)
                _copy_verified_file(file_path, destination_file, image.content_digest)
                result.files_exported += 1
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to export favorite image %s", display_file(file_path))
            progress.update(process, advance=1)

    return result


def _copy_verified_file(source: Path, destination: Path, expected_digest: str) -> None:
    temporary_destination = destination.with_name(
        f".{destination.stem}.{uuid4().hex}{destination.suffix}"
    )
    try:
        copy_file_preserving_metadata(source, temporary_destination)
        if get_content_digest(temporary_destination) != expected_digest:
            raise shared.SessionProcessError(
                f"Staged export verification failed: {source}"
            )
        temporary_destination.replace(destination)
    finally:
        if temporary_destination.exists():
            temporary_destination.unlink()
