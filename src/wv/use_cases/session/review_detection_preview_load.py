from dataclasses import dataclass, field
from pathlib import Path

from wv.core.session import DETECTION_LABELS, normalize_detection_label
from wv.domain.session import SessionImage
from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared


@dataclass
class ReviewDetectionPreviewItem:
    image_id: str
    file_path: Path
    current_label: str
    reviewed: bool
    current_relative_path: str


@dataclass(frozen=True)
class LoadReviewDetectionPreviewInput:
    session_id: str
    include_reviewed: bool = False
    detection_label: str | None = None


@dataclass(frozen=True)
class LoadReviewDetectionPreviewResult:
    session_id: str
    session_path: Path
    label_counts: dict[str, int]
    items: list[ReviewDetectionPreviewItem] = field(default_factory=list)


def run(input_data: LoadReviewDetectionPreviewInput) -> LoadReviewDetectionPreviewResult:
    """Load one detection label and aggregate preview counts.

    Args:
        input_data: Session identifier and reviewed-image inclusion preference.

    Returns:
        Inventory-backed items for the requested label and counts for every label.

    Raises:
        SessionError: If the session cannot be resolved or detection is incomplete.
        SessionProcessError: If an inventory file is missing.
    """
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    states = tuple(f"detection/{label}" for label in DETECTION_LABELS)

    detection_label = (
        None
        if input_data.detection_label is None
        else _normalize_label(input_data.detection_label)
    )
    with sql_session_scope(managed_session.database_path) as sql_session:
        repository = SessionImageRepository(sql_session)
        counts = repository.count_by_state_for_session(
            managed_session.session.id,
            states=states,
            detection_reviewed=None if input_data.include_reviewed else False,
        )
        images = (
            []
            if detection_label is None
            else repository.list_for_session_state(
                managed_session.session.id,
                f"detection/{detection_label}",
                detection_reviewed=None if input_data.include_reviewed else False,
            )
        )

    return LoadReviewDetectionPreviewResult(
        session_id=managed_session.session.id,
        session_path=managed_session.session_path,
        label_counts={
            label: next(
                (count.count for count in counts if count.state == f"detection/{label}"),
                0,
            )
            for label in DETECTION_LABELS
        },
        items=[_to_item(managed_session.session_path, image) for image in images],
    )


def _to_item(session_path: Path, image: SessionImage) -> ReviewDetectionPreviewItem:
    file_path = shared._resolve_session_path(session_path, image.current_relative_path)
    if not file_path.is_file():
        raise shared.SessionProcessError(
            f"Image inventory file is missing for {image.id}: {file_path}"
        )
    return ReviewDetectionPreviewItem(
        image_id=image.id,
        file_path=file_path,
        current_label=_label_from_state(image.state),
        reviewed=image.detection_reviewed,
        current_relative_path=image.current_relative_path,
    )


def _label_from_state(state: str) -> str:
    _, label = state.split("/", maxsplit=1)
    return label


def _normalize_label(label: str) -> str:
    try:
        return normalize_detection_label(label)
    except ValueError as exc:
        raise shared.SessionError(f"Unsupported review label: {label}") from exc
