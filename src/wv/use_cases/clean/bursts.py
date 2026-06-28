from dataclasses import dataclass
from pathlib import Path
from pydoc import source_synopsis

from wv.core.files import ensure_directory


@dataclass(frozen=True)
class CleanBurstsInput:
    source: Path
    output: Path
    burst_gap_threshold: int
    similarity_threshold: int
    dry_run: bool = False


@dataclass
class CleanBurstsResult:
    files_discovered: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_bursts: int = 0
    files_reduced: int = 0
    files_failed: int = 0
    destination: Path = Path()
    dry_run: bool = False


def run(input_data: CleanBurstsInput) -> None:
    destination = input_data.output / "ignored" / "redundant"
    result = CleanBurstsResult(destination=destination, dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())

    result.files_discovered = len(source_files)

    pass
