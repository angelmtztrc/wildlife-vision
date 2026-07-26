from dataclasses import dataclass, field
from pathlib import Path

from wv.core.files import ensure_directory, is_allowed_image_file

from . import _shared as shared


@dataclass
class ReviewItem:
    file_path: Path
    original_label: str
    reviewed: bool


@dataclass(frozen=True)
class LoadReviewSessionInput:
    session_path: Path
    detection_label: str
    pending_only: bool = False


@dataclass
class LoadReviewSessionResult:
    source_directory: Path
    items: list[ReviewItem] = field(default_factory=list)
    files_ignored: int = 0


def run(input_data: LoadReviewSessionInput) -> LoadReviewSessionResult:
    detection_label = shared.normalize_review_label(input_data.detection_label)
    ensure_directory(input_data.session_path)

    source_directory = shared.detection_directory(input_data.session_path, detection_label)
    ensure_directory(source_directory)

    result = LoadReviewSessionResult(source_directory=source_directory)

    for file_path in sorted(source_directory.iterdir(), key=lambda path: path.name.lower()):
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        reviewed = shared.is_reviewed(file_path)
        if input_data.pending_only and reviewed:
            continue

        result.items.append(
            ReviewItem(
                file_path=file_path,
                original_label=detection_label,
                reviewed=reviewed,
            )
        )

    return result
