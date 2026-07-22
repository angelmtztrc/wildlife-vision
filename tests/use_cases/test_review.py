from pathlib import Path

import pytest

import wv.use_cases.review as review
from wv.core.exif import read_exif
from wv.use_cases.review import (
    ApplyReviewDecision,
    ApplyReviewInput,
    LoadReviewSessionInput,
    apply_review,
    load_review_session,
)


def test_load_review_session_filters_pending_only(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)

    reviewed = make_image(
        animal_path / "reviewed.jpg",
        exif={"ImageDescription": "Detection=animal;Reviewed=true;"},
    )
    pending = make_image(animal_path / "pending.jpg")
    (animal_path / "notes.txt").write_text("ignore")

    result = load_review_session(
        LoadReviewSessionInput(
            session_path=session_path,
            detection_label="animal",
            pending_only=True,
        )
    )

    assert result.source_directory == animal_path
    assert result.files_ignored == 1
    assert [item.file_path for item in result.items] == [pending]
    assert reviewed not in [item.file_path for item in result.items]


def test_apply_review_same_label_writes_metadata_only(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    result = apply_review(
        ApplyReviewInput(
            session_path=session_path,
            decisions=[
                ApplyReviewDecision(
                    file_path=image_path,
                    source_label="animal",
                    target_label="animal",
                )
            ],
        )
    )

    assert result.files_reviewed == 1
    assert result.files_reassigned == 0
    assert result.files_moved == 0
    assert result.files_failed == 0
    assert image_path.exists()
    assert read_exif(image_path, "ImageDescription") == "Detection=animal;Reviewed=true;"


def test_apply_review_relabels_and_moves_file(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    result = apply_review(
        ApplyReviewInput(
            session_path=session_path,
            decisions=[
                ApplyReviewDecision(
                    file_path=image_path,
                    source_label="animal",
                    target_label="human",
                )
            ],
        )
    )

    destination = session_path / "detection" / "human" / "animal.jpg"
    assert result.files_reviewed == 1
    assert result.files_reassigned == 1
    assert result.files_moved == 1
    assert result.files_failed == 0
    assert destination.exists()
    assert not image_path.exists()
    assert read_exif(destination, "ImageDescription") == "Detection=human;Reviewed=true;"


def test_apply_review_counts_replacements(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    human_path = session_path / "detection" / "human"
    animal_path.mkdir(parents=True)
    human_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")
    make_image(human_path / "animal.jpg")

    result = apply_review(
        ApplyReviewInput(
            session_path=session_path,
            decisions=[
                ApplyReviewDecision(
                    file_path=image_path,
                    source_label="animal",
                    target_label="human",
                )
            ],
        )
    )

    assert result.files_reviewed == 1
    assert result.files_replaced == 1
    assert result.files_failed == 0


def test_apply_review_reports_metadata_failures(make_image, tmp_path: Path, monkeypatch):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    monkeypatch.setattr(
        review,
        "write_exif_image_description",
        lambda file_path, data: (_ for _ in ()).throw(OSError("metadata write failed")),
    )

    result = apply_review(
        ApplyReviewInput(
            session_path=session_path,
            decisions=[
                ApplyReviewDecision(
                    file_path=image_path,
                    source_label="animal",
                    target_label="animal",
                )
            ],
        )
    )

    assert result.files_reviewed == 0
    assert result.files_failed == 1
    assert image_path.exists()
    assert result.item_results[0].failure == "metadata write failed"
