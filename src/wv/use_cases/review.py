from dataclasses import dataclass, field
from pathlib import Path
import shutil
from uuid import uuid4

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.metadata import parse_image_description, upsert_image_description_properties
from wv.core.session import DETECTION_LABELS, get_detection_path

REVIEW_LABELS = DETECTION_LABELS


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


@dataclass(frozen=True)
class ApplyReviewDecision:
    file_path: Path
    source_label: str
    target_label: str


@dataclass(frozen=True)
class ApplyReviewInput:
    session_path: Path
    decisions: list[ApplyReviewDecision]


@dataclass
class ApplyReviewItemResult:
    original_path: Path
    final_path: Path
    source_label: str
    target_label: str
    moved: bool
    replaced_existing: bool
    success: bool
    failure: str | None = None


@dataclass
class ApplyReviewResult:
    files_reviewed: int = 0
    files_reassigned: int = 0
    files_moved: int = 0
    files_replaced: int = 0
    files_failed: int = 0
    item_results: list[ApplyReviewItemResult] = field(default_factory=list)


def normalize_review_label(label: str) -> str:
    normalized = label.strip().lower()
    if normalized not in REVIEW_LABELS:
        raise ValueError(f"Unsupported review label: {label}")
    return normalized


def _review_metadata(file_path: Path) -> dict[str, str]:
    return parse_image_description(read_exif(file_path, "ImageDescription"))


def _is_reviewed(file_path: Path) -> bool:
    return _review_metadata(file_path).get("Reviewed", "").lower() == "true"


def _detection_directory(session_path: Path, detection_label: str) -> Path:
    return get_detection_path(session_path, detection_label)


def _move_source_to_destination(source: Path, destination: Path) -> tuple[bool, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)

    replaced_existing = destination.exists()
    temp_destination = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    try:
        shutil.move(str(source), temp_destination)
        temp_destination.replace(destination)
        return True, replaced_existing
    finally:
        if temp_destination.exists():
            temp_destination.unlink()


def load_review_session(input_data: LoadReviewSessionInput) -> LoadReviewSessionResult:
    detection_label = normalize_review_label(input_data.detection_label)
    ensure_directory(input_data.session_path)

    source_directory = _detection_directory(input_data.session_path, detection_label)
    ensure_directory(source_directory)

    result = LoadReviewSessionResult(source_directory=source_directory)

    for file_path in sorted(source_directory.iterdir(), key=lambda path: path.name.lower()):
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        reviewed = _is_reviewed(file_path)
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


def apply_review(input_data: ApplyReviewInput) -> ApplyReviewResult:
    ensure_directory(input_data.session_path)
    result = ApplyReviewResult()

    for decision in input_data.decisions:
        source_label = normalize_review_label(decision.source_label)
        target_label = normalize_review_label(decision.target_label)
        final_path = _detection_directory(input_data.session_path, target_label) / decision.file_path.name

        try:
            updated_description = upsert_image_description_properties(
                read_exif(decision.file_path, "ImageDescription"),
                {
                    "Detection": target_label,
                    "Reviewed": "true",
                },
            )
            write_exif_image_description(decision.file_path, updated_description)

            moved = False
            replaced_existing = False
            committed_path = decision.file_path
            if target_label != source_label:
                moved, replaced_existing = _move_source_to_destination(
                    source=decision.file_path,
                    destination=final_path,
                )
                committed_path = final_path

            result.files_reviewed += 1
            if target_label != source_label:
                result.files_reassigned += 1
            if moved:
                result.files_moved += 1
            if replaced_existing:
                result.files_replaced += 1

            result.item_results.append(
                ApplyReviewItemResult(
                    original_path=decision.file_path,
                    final_path=committed_path,
                    source_label=source_label,
                    target_label=target_label,
                    moved=moved,
                    replaced_existing=replaced_existing,
                    success=True,
                )
            )
        except Exception as exc:
            result.files_failed += 1
            result.item_results.append(
                ApplyReviewItemResult(
                    original_path=decision.file_path,
                    final_path=final_path,
                    source_label=source_label,
                    target_label=target_label,
                    moved=False,
                    replaced_existing=False,
                    success=False,
                    failure=str(exc),
                )
            )

    return result
