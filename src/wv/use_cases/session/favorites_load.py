from dataclasses import dataclass, field
from pathlib import Path

from wv.domain.session import SessionImage
from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared


@dataclass
class FavoriteItem:
    image_id: str
    file_path: Path
    is_favorite: bool
    reviewed: bool


@dataclass(frozen=True)
class LoadFavoritesInput:
    session_id: str
    pending_only: bool = False


@dataclass(frozen=True)
class LoadFavoritesResult:
    session_id: str
    source_directory: Path
    items: list[FavoriteItem] = field(default_factory=list)


def run(input_data: LoadFavoritesInput) -> LoadFavoritesResult:
    """Load animal detections for database-backed favorite review."""
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    with sql_session_scope(managed_session.database_path) as sql_session:
        images = SessionImageRepository(sql_session).list_for_session_state(
            managed_session.session.id,
            "detection/animal",
            favorite_reviewed=False if input_data.pending_only else None,
        )
    return LoadFavoritesResult(
        session_id=managed_session.session.id,
        source_directory=managed_session.session_path / "detection" / "animal",
        items=[_to_item(managed_session.session_path, image) for image in images],
    )


def _to_item(session_path: Path, image: SessionImage) -> FavoriteItem:
    file_path = shared._resolve_session_path(session_path, image.current_relative_path)
    if not file_path.is_file():
        raise shared.SessionProcessError(
            f"Image inventory file is missing for {image.id}: {file_path}"
        )
    return FavoriteItem(
        image_id=image.id,
        file_path=file_path,
        is_favorite=image.is_favorite,
        reviewed=image.favorite_reviewed,
    )
