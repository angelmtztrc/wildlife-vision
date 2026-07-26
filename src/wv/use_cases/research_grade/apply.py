from dataclasses import dataclass, field
from pathlib import Path

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory
from wv.core.metadata import upsert_image_description_properties

from . import _shared as shared


@dataclass(frozen=True)
class ApplyResearchGradeDecision:
    file_path: Path
    research_grade: bool


@dataclass(frozen=True)
class ApplyResearchGradeInput:
    session_path: Path
    decisions: list[ApplyResearchGradeDecision]


@dataclass
class ApplyResearchGradeItemResult:
    file_path: Path
    research_grade: bool
    success: bool
    failure: str | None = None


@dataclass
class ApplyResearchGradeResult:
    files_updated: int = 0
    files_flagged: int = 0
    files_unflagged: int = 0
    files_failed: int = 0
    item_results: list[ApplyResearchGradeItemResult] = field(default_factory=list)


def run(input_data: ApplyResearchGradeInput) -> ApplyResearchGradeResult:
    ensure_directory(input_data.session_path)
    result = ApplyResearchGradeResult()

    for decision in input_data.decisions:
        try:
            updated_description = upsert_image_description_properties(
                read_exif(decision.file_path, "ImageDescription"),
                {
                    "Research_Grade": (
                        shared.RESEARCH_GRADE_TRUE
                        if decision.research_grade
                        else shared.RESEARCH_GRADE_FALSE
                    )
                },
            )
            write_exif_image_description(decision.file_path, updated_description)

            result.files_updated += 1
            if decision.research_grade:
                result.files_flagged += 1
            else:
                result.files_unflagged += 1

            result.item_results.append(
                ApplyResearchGradeItemResult(
                    file_path=decision.file_path,
                    research_grade=decision.research_grade,
                    success=True,
                )
            )
        except Exception as exc:
            result.files_failed += 1
            result.item_results.append(
                ApplyResearchGradeItemResult(
                    file_path=decision.file_path,
                    research_grade=decision.research_grade,
                    success=False,
                    failure=str(exc),
                )
            )

    return result
