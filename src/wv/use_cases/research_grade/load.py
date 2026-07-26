from dataclasses import dataclass, field
from pathlib import Path

from wv.core.files import ensure_directory, is_allowed_image_file

from . import _shared as shared


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


def run(input_data: LoadResearchGradeSessionInput) -> LoadResearchGradeSessionResult:
    ensure_directory(input_data.session_path)

    source_directory = shared.animal_detection_directory(input_data.session_path)
    ensure_directory(source_directory)

    result = LoadResearchGradeSessionResult(source_directory=source_directory)

    for file_path in sorted(source_directory.iterdir(), key=lambda path: path.name.lower()):
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        research_grade = shared.read_research_grade(file_path)
        if input_data.pending_only and research_grade is not None:
            continue

        result.items.append(
            ResearchGradeItem(file_path=file_path, research_grade=research_grade)
        )

    return result
