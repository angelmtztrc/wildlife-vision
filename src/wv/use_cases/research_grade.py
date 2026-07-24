from dataclasses import dataclass, field
from pathlib import Path

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.metadata import parse_image_description, upsert_image_description_properties
from wv.core.session import get_detection_path

RESEARCH_GRADE_TRUE = "true"
RESEARCH_GRADE_FALSE = "false"


@dataclass
class ResearchGradeItem:
    file_path: Path
    research_grade: bool | None


@dataclass(frozen=True)
class LoadResearchGradeSessionInput:
    session_path: Path
    pending_only: bool = False


@dataclass
class LoadResearchGradeSessionResult:
    source_directory: Path
    items: list[ResearchGradeItem] = field(default_factory=list)
    files_ignored: int = 0


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


def _animal_detection_directory(session_path: Path) -> Path:
    return get_detection_path(session_path, "animal")


def _research_grade_metadata(file_path: Path) -> dict[str, str]:
    return parse_image_description(read_exif(file_path, "ImageDescription"))


def _parse_research_grade(value: str | None) -> bool | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized == RESEARCH_GRADE_TRUE:
        return True
    if normalized == RESEARCH_GRADE_FALSE:
        return False
    return None


def _read_research_grade(file_path: Path) -> bool | None:
    return _parse_research_grade(_research_grade_metadata(file_path).get("Research_Grade"))


def load_research_grade_session(
    input_data: LoadResearchGradeSessionInput,
) -> LoadResearchGradeSessionResult:
    ensure_directory(input_data.session_path)

    source_directory = _animal_detection_directory(input_data.session_path)
    ensure_directory(source_directory)

    result = LoadResearchGradeSessionResult(source_directory=source_directory)

    for file_path in sorted(source_directory.iterdir(), key=lambda path: path.name.lower()):
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        research_grade = _read_research_grade(file_path)
        if input_data.pending_only and research_grade is not None:
            continue

        result.items.append(
            ResearchGradeItem(file_path=file_path, research_grade=research_grade)
        )

    return result


def apply_research_grade(input_data: ApplyResearchGradeInput) -> ApplyResearchGradeResult:
    ensure_directory(input_data.session_path)
    result = ApplyResearchGradeResult()

    for decision in input_data.decisions:
        try:
            updated_description = upsert_image_description_properties(
                read_exif(decision.file_path, "ImageDescription"),
                {
                    "Research_Grade": (
                        RESEARCH_GRADE_TRUE
                        if decision.research_grade
                        else RESEARCH_GRADE_FALSE
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
