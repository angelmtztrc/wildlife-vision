from dataclasses import dataclass, field
from pathlib import Path

from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared


@dataclass(frozen=True)
class ApplyFavoriteDecision:
    image_id: str
    is_favorite: bool


@dataclass(frozen=True)
class ApplyFavoritesInput:
    session_id: str
    decisions: list[ApplyFavoriteDecision]


@dataclass(frozen=True)
class ApplyFavoriteItemResult:
    image_id: str
    file_path: Path
    is_favorite: bool
    success: bool
    failure: str | None = None


@dataclass
class ApplyFavoritesResult:
    files_updated: int = 0
    files_favorited: int = 0
    files_unfavorited: int = 0
    files_failed: int = 0
    item_results: list[ApplyFavoriteItemResult] = field(default_factory=list)


def run(input_data: ApplyFavoritesInput) -> ApplyFavoritesResult:
    """Persist favorite decisions without modifying image files."""
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    result = ApplyFavoritesResult()

    with shared._exclusive_session_lock(managed_session.session_path, dry_run=False):
        for decision in input_data.decisions:
            _apply_decision(managed_session, decision, result)
    return result


def _apply_decision(
    managed_session: shared.ManagedSession,
    decision: ApplyFavoriteDecision,
    result: ApplyFavoritesResult,
) -> None:
    file_path = Path()
    try:
        with sql_session_scope(managed_session.database_path) as sql_session:
            repository = SessionImageRepository(sql_session)
            image = repository.get(decision.image_id)
            if image.session_id != managed_session.session.id:
                raise shared.SessionProcessError(
                    f"Image does not belong to session: {decision.image_id}"
                )
            if image.state != "detection/animal":
                raise shared.SessionProcessError(
                    f"Image is not an animal detection: {decision.image_id}"
                )
            file_path = shared._resolve_session_path(
                managed_session.session_path, image.current_relative_path
            )
            if not file_path.is_file():
                raise shared.SessionProcessError(
                    f"Image inventory file is missing for {decision.image_id}: {file_path}"
                )
            repository.set_favorite(image.id, decision.is_favorite)

        result.files_updated += 1
        if decision.is_favorite:
            result.files_favorited += 1
        else:
            result.files_unfavorited += 1
        result.item_results.append(
            ApplyFavoriteItemResult(
                image_id=decision.image_id,
                file_path=file_path,
                is_favorite=decision.is_favorite,
                success=True,
            )
        )
    except Exception as exc:
        result.files_failed += 1
        result.item_results.append(
            ApplyFavoriteItemResult(
                image_id=decision.image_id,
                file_path=file_path,
                is_favorite=decision.is_favorite,
                success=False,
                failure=str(exc),
            )
        )
