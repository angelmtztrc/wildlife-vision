from dataclasses import dataclass
from pathlib import Path

from wv.core.files import ensure_directory, is_allowed_image_file
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
    ensure_directory(input_data.source)

    result = IngestSdResult(dry_run=input_data.dry_run)

    for file in input_data.source.iterdir():
        if is_allowed_image_file(file):
            captured_at = get_image_datetime(file)
            print(f"{captured_at}")
            pass

        result.files_ignored += 1

    return None
