from dataclasses import dataclass, field
from pathlib import Path

from wv.core.session import normalize_detection_label
from wv.domain.session import SessionImage
from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared

@dataclass
class ReviewDetectionItem:
    image_id: str
    file_path: Path
    original_label: str
    reviewed: bool


@dataclass(frozen=True)
class LoadReviewDetectionInput:
    session_id: str
    detection_label: str
    pending_only: bool = False


@dataclass(frozen=True)
class LoadReviewDetectionResult:
    session_id: str
    source_directory: Path
    items: list[ReviewDetectionItem] = field(default_factory=list)


def run(input_data: LoadReviewDetectionInput) -> LoadReviewDetectionResult:
    """Load inventory-backed images for one completed detection bucket."""
    detection_label = _normalize_label(input_data.detection_label)
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    state = f"detection/{detection_label}"

    with sql_session_scope(managed_session.database_path) as sql_session:
        images = SessionImageRepository(sql_session).list_for_session_state(
            managed_session.session.id,
            state,
            detection_reviewed=False if input_data.pending_only else None,
        )

    items = [_to_item(managed_session.session_path, image, detection_label) for image in images]
    return LoadReviewDetectionResult(
        session_id=managed_session.session.id,
        source_directory=managed_session.session_path / "detection" / detection_label,
        items=items,
    )


def _normalize_label(label: str) -> str:
    try:
        return normalize_detection_label(label)
    except ValueError as exc:
        raise shared.SessionError(f"Unsupported review label: {label}") from exc


def _to_item(
    session_path: Path, image: SessionImage, detection_label: str
) -> ReviewDetectionItem:
    file_path = shared._resolve_session_path(session_path, image.current_relative_path)
    if not file_path.is_file():
        raise shared.SessionProcessError(
            f"Image inventory file is missing for {image.id}: {file_path}"
        )
    return ReviewDetectionItem(
        image_id=image.id,
        file_path=file_path,
        original_label=detection_label,
        reviewed=image.detection_reviewed,
    )
