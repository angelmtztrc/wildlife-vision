from dataclasses import dataclass, field
from pathlib import Path

from wv.core.files import get_content_digest, move_file_with_staged_copy
from wv.core.session import normalize_detection_label
from wv.persistence.repositories import SessionImageRepository
from wv.persistence.sql_session import sql_session_scope

from . import _shared as shared

@dataclass(frozen=True)
class ApplyReviewDetectionDecision:
    image_id: str
    source_label: str
    target_label: str


@dataclass(frozen=True)
class ApplyReviewDetectionInput:
    session_id: str
    decisions: list[ApplyReviewDetectionDecision]


@dataclass(frozen=True)
class ApplyReviewDetectionItemResult:
    image_id: str
    original_path: Path
    final_path: Path
    source_label: str
    target_label: str
    moved: bool
    success: bool
    failure: str | None = None


@dataclass
class ApplyReviewDetectionResult:
    files_reviewed: int = 0
    files_reassigned: int = 0
    files_moved: int = 0
    files_failed: int = 0
    item_results: list[ApplyReviewDetectionItemResult] = field(default_factory=list)


def run(input_data: ApplyReviewDetectionInput) -> ApplyReviewDetectionResult:
    """Persist detection review decisions and relocate corrected image files."""
    managed_session = shared.resolve_managed_session(input_data.session_id)
    shared.require_completed_detection(managed_session)
    result = ApplyReviewDetectionResult()

    with shared._exclusive_session_lock(managed_session.session_path, dry_run=False):
        for decision in input_data.decisions:
            _apply_decision(managed_session, decision, result)
    return result


def _apply_decision(
    managed_session: shared.ManagedSession,
    decision: ApplyReviewDetectionDecision,
    result: ApplyReviewDetectionResult,
) -> None:
    source_label = _normalize_label(decision.source_label)
    target_label = _normalize_label(decision.target_label)
    original_path = Path()
    final_path = Path()
    moved = False

    try:
        with sql_session_scope(managed_session.database_path) as sql_session:
            repository = SessionImageRepository(sql_session)
            image = repository.get(decision.image_id)
            if image.session_id != managed_session.session.id:
                raise shared.SessionProcessError(
                    f"Image does not belong to session: {decision.image_id}"
                )
            if image.state != f"detection/{source_label}":
                raise shared.SessionProcessError(
                    f"Image state changed since loading: {decision.image_id}"
                )

            original_path = shared._resolve_session_path(
                managed_session.session_path, image.current_relative_path
            )
            if not original_path.is_file():
                raise shared.SessionProcessError(
                    f"Image inventory file is missing for {decision.image_id}: {original_path}"
                )

            if source_label == target_label:
                repository.mark_detection_reviewed(image.id)
                final_path = original_path
            else:
                target_relative_path = f"detection/{target_label}/{original_path.name}"
                final_path = shared._resolve_session_path(
                    managed_session.session_path, target_relative_path
                )
                if final_path.exists():
                    raise shared.SessionProcessError(
                        f"Detection destination already exists: {final_path}"
                    )
                if get_content_digest(original_path) != image.content_digest or (
                    original_path.stat().st_size != image.content_size_bytes
                ):
                    raise shared.SessionProcessError(
                        f"Image content differs from inventory: {original_path}"
                    )

                move_file_with_staged_copy(
                    original_path,
                    final_path,
                    verify=lambda staged: staged.stat().st_size == image.content_size_bytes
                    and get_content_digest(staged) == image.content_digest,
                )
                moved = True
                try:
                    repository.relocate_reviewed(image.id, target_relative_path, f"detection/{target_label}")
                except Exception:
                    if final_path.is_file() and not original_path.exists():
                        final_path.replace(original_path)
                    raise

        result.files_reviewed += 1
        if moved:
            result.files_reassigned += 1
            result.files_moved += 1
        result.item_results.append(
            ApplyReviewDetectionItemResult(
                image_id=decision.image_id,
                original_path=original_path,
                final_path=final_path,
                source_label=source_label,
                target_label=target_label,
                moved=moved,
                success=True,
            )
        )
    except Exception as exc:
        if moved and final_path.is_file() and not original_path.exists():
            try:
                final_path.replace(original_path)
            except OSError:
                pass
        result.files_failed += 1
        result.item_results.append(
            ApplyReviewDetectionItemResult(
                image_id=decision.image_id,
                original_path=original_path,
                final_path=final_path,
                source_label=source_label,
                target_label=target_label,
                moved=False,
                success=False,
                failure=str(exc),
            )
        )


def _normalize_label(label: str) -> str:
    try:
        return normalize_detection_label(label)
    except ValueError as exc:
        raise shared.SessionError(f"Unsupported review label: {label}") from exc

