from pathlib import Path

import pytest

from wv.core.files import get_content_digest
from wv.domain.session import IngestSession, SessionImage
from wv.persistence.repositories import (
    SessionImageRepository,
    SessionProcessRepository,
    SessionRepository,
)
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.session.export_favorites import ExportFavoritesInput, run as export_favorites
from wv.use_cases.session import _shared as shared
from wv.use_cases.session.favorites_apply import (
    ApplyFavoriteDecision,
    ApplyFavoritesInput,
    run as apply_favorites,
)
from wv.use_cases.session.favorites_load import LoadFavoritesInput, run as load_favorites
from wv.use_cases.session.review_detection_apply import (
    ApplyReviewDetectionDecision,
    ApplyReviewDetectionInput,
    run as apply_review_detection,
)
from wv.use_cases.session.review_detection_load import (
    LoadReviewDetectionInput,
    run as load_review_detection,
)

SESSION_ID = "20240628_120000__HNT001"


def _create_detected_session(
    workspace_path: Path, make_image, *, process_status: str = "completed"
) -> tuple[Path, Path]:
    session_path = workspace_path / "sessions" / SESSION_ID
    (session_path / "init").mkdir(parents=True)
    animal_path = make_image(session_path / "detection" / "animal" / "animal.jpg")
    database_path = workspace_path / ".wv" / "database.sqlite"

    with sql_session_scope(database_path) as sql_session:
        SessionRepository(sql_session).create(
            IngestSession(
                id=SESSION_ID,
                monitoring_site_id="SITE001",
                source_path="/source",
                mode="copy",
                recursive=False,
                started_at="2026-08-08T00:00:00+00:00",
                ingest_status="completed",
            )
        )
        SessionImageRepository(sql_session).create_or_replace_by_initial_path(
            SessionImage(
                id="image-1",
                session_id=SESSION_ID,
                source_relative_path="DCIM/animal.jpg",
                initial_relative_path="init/animal.jpg",
                current_relative_path="detection/animal/animal.jpg",
                state="detection/animal",
                content_digest=get_content_digest(animal_path),
                content_size_bytes=animal_path.stat().st_size,
                captured_at="2024-06-28T12:00:00+00:00",
                ingested_at="2026-08-08T00:00:00+00:00",
            )
        )
        processes = SessionProcessRepository(sql_session)
        processes.start(SESSION_ID, "detect_content", "2026-08-08T00:01:00+00:00", "{}")
        processes.complete(
            SESSION_ID,
            "detect_content",
            status=process_status,
            completed_at="2026-08-08T00:02:00+00:00",
            files_discovered=1,
            files_processed=1,
            files_selected=1,
            files_moved=1,
            files_ignored=0,
            files_failed=0,
        )
    return session_path, animal_path


def test_favorites_update_database_without_changing_image(
    configured_workspace: Path, make_image
):
    _, animal_path = _create_detected_session(configured_workspace, make_image)
    original_bytes = animal_path.read_bytes()

    loaded = load_favorites(LoadFavoritesInput(session_id=SESSION_ID, pending_only=True))
    assert [item.image_id for item in loaded.items] == ["image-1"]

    result = apply_favorites(
        ApplyFavoritesInput(
            session_id=SESSION_ID,
            decisions=[ApplyFavoriteDecision(image_id="image-1", is_favorite=True)],
        )
    )

    assert result.files_favorited == 1
    assert animal_path.read_bytes() == original_bytes
    with sql_session_scope(configured_workspace / ".wv" / "database.sqlite") as sql_session:
        image = SessionImageRepository(sql_session).get("image-1")
    assert image.is_favorite is True
    assert image.favorite_reviewed is True
    assert not load_favorites(LoadFavoritesInput(session_id=SESSION_ID, pending_only=True)).items


def test_detection_review_relocates_inventory_without_modifying_exif(
    configured_workspace: Path, make_image
):
    session_path, animal_path = _create_detected_session(configured_workspace, make_image)
    original_bytes = animal_path.read_bytes()
    apply_favorites(
        ApplyFavoritesInput(
            session_id=SESSION_ID,
            decisions=[ApplyFavoriteDecision(image_id="image-1", is_favorite=True)],
        )
    )

    result = apply_review_detection(
        ApplyReviewDetectionInput(
            session_id=SESSION_ID,
            decisions=[
                ApplyReviewDetectionDecision(
                    image_id="image-1", source_label="animal", target_label="human"
                )
            ],
        )
    )

    human_path = session_path / "detection" / "human" / "animal.jpg"
    assert result.files_moved == 1
    assert not animal_path.exists()
    assert human_path.read_bytes() == original_bytes
    with sql_session_scope(configured_workspace / ".wv" / "database.sqlite") as sql_session:
        image = SessionImageRepository(sql_session).get("image-1")
    assert image.current_relative_path == "detection/human/animal.jpg"
    assert image.state == "detection/human"
    assert image.detection_reviewed is True
    assert image.is_favorite is False
    assert image.favorite_reviewed is False


def test_completed_detection_with_failures_allows_review(
    configured_workspace: Path, make_image
):
    _create_detected_session(
        configured_workspace, make_image, process_status="completed_with_failures"
    )

    result = load_review_detection(
        LoadReviewDetectionInput(session_id=SESSION_ID, detection_label="animal")
    )

    assert [item.image_id for item in result.items] == ["image-1"]


def test_review_and_favorites_require_completed_detection(
    configured_workspace: Path, make_image
):
    _create_detected_session(configured_workspace, make_image, process_status="failed")

    with pytest.raises(shared.SessionProcessError, match="Detection must complete"):
        load_review_detection(
            LoadReviewDetectionInput(session_id=SESSION_ID, detection_label="animal")
        )
    with pytest.raises(shared.SessionProcessError, match="Detection must complete"):
        load_favorites(LoadFavoritesInput(session_id=SESSION_ID))


def test_export_favorites_uses_database_state(configured_workspace: Path, make_image, tmp_path: Path):
    _, animal_path = _create_detected_session(configured_workspace, make_image)
    apply_favorites(
        ApplyFavoritesInput(
            session_id=SESSION_ID,
            decisions=[ApplyFavoriteDecision(image_id="image-1", is_favorite=True)],
        )
    )
    destination = tmp_path / "exports"

    result = export_favorites(
        ExportFavoritesInput(session_id=SESSION_ID, output=destination)
    )

    assert result.files_exported == 1
    assert (destination / animal_path.name).read_bytes() == animal_path.read_bytes()
