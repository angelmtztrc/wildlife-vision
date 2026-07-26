from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session as SqlSession

from wv.core.files import copy_file_preserving_metadata, get_file_id
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import DeviceRepository, MonitoringSiteRepository


class IngestError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedIngestIdentity:
    device_id: str
    monitoring_site_id: str


def validate_explicit_identity(
    sql_session: SqlSession, device_id: str, monitoring_site_id: str
) -> ResolvedIngestIdentity:
    try:
        DeviceRepository(sql_session).get(device_id)
        MonitoringSiteRepository(sql_session).get(monitoring_site_id)
    except RecordNotFoundError as exc:
        raise IngestError(str(exc)) from exc

    return ResolvedIngestIdentity(
        device_id=device_id,
        monitoring_site_id=monitoring_site_id,
    )


def validate_sd_identity(
    sql_session: SqlSession,
    source: Path,
    device_id: str,
    monitoring_site_id: str,
) -> ResolvedIngestIdentity:
    try:
        device = DeviceRepository(sql_session).get(device_id)
        MonitoringSiteRepository(sql_session).get(monitoring_site_id)
    except RecordNotFoundError as exc:
        raise IngestError(str(exc)) from exc

    if device.monitoring_site_id != monitoring_site_id:
        raise IngestError(
            "SD card deployment does not match the workspace database. "
            f"Run 'wv sd sync {source.resolve()}' to synchronize the workspace from this SD card."
        )
    return ResolvedIngestIdentity(
        device_id=device_id,
        monitoring_site_id=monitoring_site_id,
    )


def get_session_path(workspace_path: Path, device_id: str, dry_run: bool) -> Path:
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


def verify_copy(source_file_id: str, copied_file: Path) -> bool:
    return get_file_id(copied_file) == source_file_id


def replace_destination_with_verified_copy(
    source: Path, destination: Path, source_file_id: str
) -> tuple[bool, bool]:
    temp_destination = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    try:
        copy_file_preserving_metadata(source, temp_destination)

        if not verify_copy(source_file_id, temp_destination):
            raise ValueError(f"Copied file verification failed for: {source}")

        replaced_existing = destination.exists()
        temp_destination.replace(destination)
        return True, replaced_existing
    finally:
        if temp_destination.exists():
            temp_destination.unlink()
