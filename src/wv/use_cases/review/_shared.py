from pathlib import Path

from wv.core.exif import read_exif
from wv.core.metadata import parse_image_description
from wv.core.session import get_detection_path, normalize_detection_label


def normalize_review_label(label: str) -> str:
    try:
        return normalize_detection_label(label)
    except ValueError as exc:
        raise ValueError(f"Unsupported review label: {label}") from exc


def review_metadata(file_path: Path) -> dict[str, str]:
    return parse_image_description(read_exif(file_path, "ImageDescription"))


def is_reviewed(file_path: Path) -> bool:
    return review_metadata(file_path).get("Reviewed", "").lower() == "true"


def detection_directory(session_path: Path, detection_label: str) -> Path:
    return get_detection_path(session_path, detection_label)
