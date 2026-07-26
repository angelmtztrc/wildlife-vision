from pathlib import Path

from wv.core.exif import read_exif
from wv.core.metadata import parse_image_description
from wv.core.session import get_detection_path

RESEARCH_GRADE_TRUE = "true"
RESEARCH_GRADE_FALSE = "false"


def animal_detection_directory(session_path: Path) -> Path:
    return get_detection_path(session_path, "animal")


def research_grade_metadata(file_path: Path) -> dict[str, str]:
    return parse_image_description(read_exif(file_path, "ImageDescription"))


def parse_research_grade(value: str | None) -> bool | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized == RESEARCH_GRADE_TRUE:
        return True
    if normalized == RESEARCH_GRADE_FALSE:
        return False
    return None


def read_research_grade(file_path: Path) -> bool | None:
    return parse_research_grade(research_grade_metadata(file_path).get("Research_Grade"))
