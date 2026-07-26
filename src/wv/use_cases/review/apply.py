from dataclasses import dataclass, field
from pathlib import Path

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, move_file_with_staged_copy
from wv.core.metadata import upsert_image_description_properties

from . import _shared as shared


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


def run(input_data: ApplyReviewInput) -> ApplyReviewResult:
    ensure_directory(input_data.session_path)
    result = ApplyReviewResult()

    for decision in input_data.decisions:
        source_label = shared.normalize_review_label(decision.source_label)
        target_label = shared.normalize_review_label(decision.target_label)
        final_path = shared.detection_directory(input_data.session_path, target_label) / decision.file_path.name

        try:
            updated_description = upsert_image_description_properties(
                read_exif(decision.file_path, "ImageDescription"),
                {
                    "Detection": target_label,
                    "Reviewed": "true",
                },
            )
            moved = False
            replaced_existing = False
            committed_path = decision.file_path
            if target_label != source_label:
                def _write_review_metadata(staged_file: Path) -> None:
                    write_exif_image_description(staged_file, updated_description)

                moved, replaced_existing = move_file_with_staged_copy(
                    source=decision.file_path,
                    destination=final_path,
                    transform=_write_review_metadata,
                )
                committed_path = final_path
            else:
                write_exif_image_description(decision.file_path, updated_description)

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
