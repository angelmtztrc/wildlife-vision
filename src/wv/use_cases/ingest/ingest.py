from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from wv.core.display import display_file, display_path
from wv.core.files import (
    SymlinkPathError,
    ensure_directory,
    ensure_not_symlink,
    ensure_tree_has_no_symlinks,
    get_content_digest,
    is_allowed_image_file,
)
from wv.core.images import get_image_datetime
from wv.core.logger import get_logger, get_progress
from wv.core.sd_config import (
    SdConfigError,
    get_sd_config_path,
    load_sd_config,
    resolve_sd_path,
)
from wv.core.session import get_init_path, require_session_component
from wv.models import IngestSession, SessionImage
from wv.persistence.database import initialize_database
from wv.persistence.repositories import SessionImageRepository, SessionRepository
from wv.persistence.sql_session import sql_session_scope
from ._shared import (
    IngestError,
    ResolvedIngestIdentity,
    get_session_path,
    replace_destination_with_verified_copy,
    validate_explicit_identity,
    validate_sd_identity,
)
from wv.workspace.workspace_config import require_workspace_database_path, require_workspace_path

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExplicitIngestIdentity:
    device_id: str
    monitoring_site_id: str


@dataclass(frozen=True)
class SdCardIngestIdentity:
    pass


@dataclass(frozen=True)
class IngestInput:
    source: Path
    mode: str
    identity: ExplicitIngestIdentity | SdCardIngestIdentity
    dry_run: bool = False
    recursive: bool = False


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


def _collect_source_files(source: Path, recursive: bool) -> list[Path]:
    if not recursive:
        return [file for file in source.iterdir() if file.name != ".wv" and file.is_file()]

    source_files: list[Path] = []
    for directory, dirnames, filenames in source.walk():
        dirnames[:] = [dirname for dirname in dirnames if dirname != ".wv"]
        for filename in filenames:
            file_path = directory / filename
            if file_path.name != ".wv" and file_path.is_file():
                source_files.append(file_path)

    return source_files


def _resolve_identity(
    input_data: IngestInput, database_path: Path, source: Path
) -> ResolvedIngestIdentity:
    if isinstance(input_data.identity, ExplicitIngestIdentity):
        with sql_session_scope(database_path) as sql_session:
            return validate_explicit_identity(
                sql_session,
                input_data.identity.device_id,
                input_data.identity.monitoring_site_id,
            )

    try:
        sd_config = load_sd_config(get_sd_config_path(source))
    except SdConfigError as exc:
        raise IngestError(str(exc)) from exc

    with sql_session_scope(database_path) as sql_session:
        return validate_sd_identity(
            sql_session,
            source,
            sd_config.device_id,
            sd_config.monitoring_site_id,
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _session_count_updates(
    result: IngestResult,
    *,
    ingest_status: str,
    completed_at: str | None,
    failure_message: str | None = None,
) -> dict[str, str | int | None]:
    return {
        "completed_at": completed_at,
        "ingest_status": ingest_status,
        "failure_message": failure_message,
        "files_discovered": result.files_discovered,
        "files_copied": result.files_copied,
        "files_deleted": result.files_deleted,
        "files_ignored": result.files_ignored,
        "files_failed": result.files_failed,
        "files_replaced": result.files_replaced,
    }


def _create_session_record(
    database_path: Path,
    *,
    session_id: str,
    device_id: str,
    monitoring_site_id: str,
    source_path: Path,
    input_data: IngestInput,
    result: IngestResult,
) -> None:
    with sql_session_scope(database_path) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=session_id,
                device_id=device_id,
                monitoring_site_id=monitoring_site_id,
                source_path=str(source_path),
                mode=input_data.mode,
                recursive=input_data.recursive,
                started_at=_utc_now(),
                files_discovered=result.files_discovered,
            )
        )


def _record_session_image(
    database_path: Path,
    *,
    session_path: Path,
    session_id: str,
    source_root: Path,
    source_file: Path,
    destination: Path,
    captured_at: datetime,
    content_digest: str,
) -> None:
    relative_destination = destination.relative_to(session_path).as_posix()
    source_relative_path = source_file.resolve().relative_to(source_root).as_posix()

    with sql_session_scope(database_path) as sql_session:
        SessionImageRepository(sql_session).create_or_replace_by_initial_path(
            SessionImage(
                id=str(uuid4()),
                session_id=session_id,
                source_relative_path=source_relative_path,
                initial_relative_path=relative_destination,
                current_relative_path=relative_destination,
                state="init",
                content_digest=content_digest,
                content_size_bytes=source_file.stat().st_size,
                captured_at=captured_at.isoformat(),
                ingested_at=_utc_now(),
            )
        )


def _update_session_record(
    database_path: Path,
    session_id: str,
    updates: dict[str, str | int | None],
) -> None:
    with sql_session_scope(database_path) as sql_session:
        SessionRepository(sql_session).update(session_id, updates)


def run(input_data: IngestInput) -> IngestResult:
    if input_data.mode not in {"drain", "copy"}:
        raise ValueError(f"Unknown ingest mode: {input_data.mode}")

    workspace_path = require_workspace_path()
    database_path = require_workspace_database_path(workspace_path)
    try:
        source = (
            resolve_sd_path(input_data.source)
            if isinstance(input_data.identity, SdCardIngestIdentity)
            else input_data.source
        )
        if isinstance(input_data.identity, ExplicitIngestIdentity):
            ensure_tree_has_no_symlinks(source)
        ensure_not_symlink(workspace_path / "sessions")
    except (FileNotFoundError, NotADirectoryError, SdConfigError, SymlinkPathError) as exc:
        raise IngestError(str(exc)) from exc

    initialize_database(database_path)
    resolved_identity = _resolve_identity(input_data, database_path, source)

    ensure_directory(source)
    device_id = require_session_component(resolved_identity.device_id, "Device ID")
    monitoring_site_id = require_session_component(
        resolved_identity.monitoring_site_id, "Monitoring site ID"
    )

    result = IngestResult(dry_run=input_data.dry_run)
    session_path = get_session_path(workspace_path, device_id, input_data.dry_run)
    session_id = session_path.name
    destination_path = get_init_path(session_path)
    if not input_data.dry_run:
        destination_path.mkdir(exist_ok=True)
    source_files = _collect_source_files(source, input_data.recursive)
    source_root = source.resolve()

    result.destination = destination_path
    result.files_discovered = len(source_files)

    if not input_data.dry_run:
        _create_session_record(
            database_path,
            session_id=session_id,
            device_id=device_id,
            monitoring_site_id=monitoring_site_id,
            source_path=source_root,
            input_data=input_data,
            result=result,
        )

    logger.info(
        "Discovered %s files; destination session path is %s",
        result.files_discovered,
        display_path(destination_path),
    )
    logger.info("Processing source files")

    with get_progress() as progress:
        process = progress.add_task("Processing source files", total=result.files_discovered)

        for file in source_files:
            if not is_allowed_image_file(file):
                result.files_ignored += 1
                logger.debug("Skipping %s: not a supported image file", display_file(file))
                progress.update(process, advance=1)
                continue

            try:
                captured_at = get_image_datetime(file)
                captured_at_parsed = captured_at.strftime("%Y%m%d_%H%M%S")
                content_digest = get_content_digest(file)
                file_id = content_digest[:6]
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

                copied, replaced_existing = replace_destination_with_verified_copy(
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

                try:
                    _record_session_image(
                        database_path,
                        session_path=session_path,
                        session_id=session_id,
                        source_root=source_root,
                        source_file=file,
                        destination=destination,
                        captured_at=captured_at,
                        content_digest=content_digest,
                    )
                except Exception as exc:
                    result.files_failed += 1
                    _update_session_record(
                        database_path,
                        session_id,
                        _session_count_updates(
                            result,
                            ingest_status="failed",
                            completed_at=_utc_now(),
                            failure_message=str(exc),
                        ),
                    )
                    logger.exception(
                        "Failed to record ingested file %s in the database",
                        display_file(destination),
                    )
                    progress.update(process, advance=1)
                    return result

                if input_data.mode == "drain":
                    file.unlink()
                    result.files_deleted += 1
                    logger.debug("Deleted source file after ingest: %s", display_file(file))

                progress.update(process, advance=1)
            except Exception:
                result.files_failed += 1
                logger.exception("Failed to ingest %s", file)
                progress.update(process, advance=1)

    if not input_data.dry_run:
        ingest_status = "completed_with_failures" if result.files_failed else "completed"
        _update_session_record(
            database_path,
            session_id,
            _session_count_updates(
                result,
                ingest_status=ingest_status,
                completed_at=_utc_now(),
            ),
        )

    return result
