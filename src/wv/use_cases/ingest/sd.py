from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wv.config import get_root_path
from wv.core.files import ensure_directory, get_file_id, is_allowed_image_file
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
    destination: Path = Path()
    dry_run: bool = False


def run(input_data: IngestSdInput) -> None:
    result = IngestSdResult(dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    root_path = get_root_path()
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = root_path / "sessions" / f"{session_timestamp}__{input_data.device}"

    for file in input_data.source.iterdir():
        result.files_discovered += 1
        if is_allowed_image_file(file):
            captured_at = get_image_datetime(file)
            captured_at_parsed = captured_at.strftime("%Y%m%d_%H%M%S")
            file_id = get_file_id(file)

            filename = f"{captured_at_parsed}__{input_data.monitoring_site.upper()}__{file_id}{file.suffix.lower()}"

            egestion_path = session_dir / "initial"

            result.destination = egestion_path

            if input_data.dry_run:
                # TODO: WHAT WE SHOULD DO?
                pass
            else:
                # TODO: MOVE FILES INTO EGESTION_PATH AND CLEAN SOURCE FOLDER IF DRAIN MODE
                result.files_copied += 1
                result.files_deleted += 1
                pass

        else:
            result.files_ignored += 1

    return None
