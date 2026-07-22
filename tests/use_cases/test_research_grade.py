from pathlib import Path

import pytest

import wv.use_cases.research_grade as research_grade
from wv.core.exif import read_exif
from wv.use_cases.research_grade import (
    ApplyResearchGradeDecision,
    ApplyResearchGradeInput,
    LoadResearchGradeSessionInput,
    apply_research_grade,
    load_research_grade_session,
)


def test_load_research_grade_session_filters_pending_only(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)

    flagged = make_image(
        animal_path / "flagged.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )
    pending = make_image(animal_path / "pending.jpg")
    (animal_path / "notes.txt").write_text("ignore")

    result = load_research_grade_session(
        LoadResearchGradeSessionInput(session_path=session_path, pending_only=True)
    )

    assert result.files_ignored == 1
    assert [item.file_path for item in result.items] == [pending]
    assert flagged not in [item.file_path for item in result.items]


def test_apply_research_grade_writes_true(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    result = apply_research_grade(
        ApplyResearchGradeInput(
            session_path=session_path,
            decisions=[ApplyResearchGradeDecision(file_path=image_path, research_grade=True)],
        )
    )

    assert result.files_updated == 1
    assert result.files_flagged == 1
    assert result.files_unflagged == 0
    assert result.files_failed == 0
    assert read_exif(image_path, "ImageDescription") == "Research_Grade=true;"


def test_apply_research_grade_writes_false(make_image, tmp_path: Path):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    result = apply_research_grade(
        ApplyResearchGradeInput(
            session_path=session_path,
            decisions=[ApplyResearchGradeDecision(file_path=image_path, research_grade=False)],
        )
    )

    assert result.files_updated == 1
    assert result.files_flagged == 0
    assert result.files_unflagged == 1
    assert result.files_failed == 0
    assert read_exif(image_path, "ImageDescription") == "Research_Grade=false;"


def test_apply_research_grade_reports_metadata_failures(
    make_image, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    session_path = tmp_path / "session"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(animal_path / "animal.jpg")

    monkeypatch.setattr(
        research_grade,
        "write_exif_image_description",
        lambda file_path, data: (_ for _ in ()).throw(OSError("metadata write failed")),
    )

    result = apply_research_grade(
        ApplyResearchGradeInput(
            session_path=session_path,
            decisions=[ApplyResearchGradeDecision(file_path=image_path, research_grade=True)],
        )
    )

    assert result.files_updated == 0
    assert result.files_failed == 1
    assert image_path.exists()
    assert result.item_results[0].failure == "metadata write failed"
