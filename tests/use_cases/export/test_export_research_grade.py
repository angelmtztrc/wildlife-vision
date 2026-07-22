from pathlib import Path

import pytest

from wv.core.exif import read_exif
from wv.use_cases.export.research_grade import ExportResearchGradeInput, run
import wv.use_cases.export.research_grade as export_research_grade


def test_run_exports_only_research_grade_true_to_default_destination(
    make_image, tmp_path: Path
):
    root_path = tmp_path / ".wv"
    session_path = root_path / "sessions" / "20240628_120000__HNT001"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)

    exported = make_image(
        animal_path / "exported.jpg",
        exif={"ImageDescription": "Research_Grade=true;Camera=HNT001;"},
    )
    make_image(
        animal_path / "not-exported.jpg",
        exif={"ImageDescription": "Research_Grade=false;"},
    )
    make_image(animal_path / "pending.jpg")
    (animal_path / "notes.txt").write_text("ignore")

    result = run(ExportResearchGradeInput(session_path=session_path))

    destination = root_path / "export" / "research-grade"
    exported_destination = destination / exported.name

    assert result.destination == destination
    assert result.files_discovered == 4
    assert result.files_export_candidates == 1
    assert result.files_exported == 1
    assert result.files_replaced == 0
    assert result.files_skipped == 3
    assert result.files_failed == 0
    assert exported_destination.exists()
    assert exported.exists()
    assert read_exif(exported_destination, "ImageDescription") == (
        "Research_Grade=true;Camera=HNT001;"
    )


def test_run_uses_custom_output_and_counts_replacements(make_image, tmp_path: Path):
    session_path = tmp_path / "sessions" / "20240628_120000__HNT001"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(
        animal_path / "animal.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )
    output = tmp_path / "custom-export"
    output.mkdir()
    replaced_destination = make_image(output / image_path.name)

    result = run(ExportResearchGradeInput(session_path=session_path, output=output))

    assert result.destination == output
    assert result.files_export_candidates == 1
    assert result.files_exported == 1
    assert result.files_replaced == 1
    assert result.files_failed == 0
    assert replaced_destination.exists()
    assert read_exif(replaced_destination, "ImageDescription") == "Research_Grade=true;"


def test_run_dry_run_counts_candidates_without_copying(make_image, tmp_path: Path):
    root_path = tmp_path / ".wv"
    session_path = root_path / "sessions" / "20240628_120000__HNT001"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    image_path = make_image(
        animal_path / "animal.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )

    result = run(ExportResearchGradeInput(session_path=session_path, dry_run=True))

    assert result.destination == root_path / "export" / "research-grade"
    assert result.files_export_candidates == 1
    assert result.files_exported == 0
    assert result.files_failed == 0
    assert result.dry_run is True
    assert image_path.exists()
    assert not result.destination.exists()


def test_run_reports_copy_failures_and_continues(
    make_image, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    session_path = tmp_path / "sessions" / "20240628_120000__HNT001"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    first = make_image(
        animal_path / "first.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )
    second = make_image(
        animal_path / "second.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )
    real_copy = export_research_grade.copy_file_preserving_metadata

    def flaky_copy(source: Path, destination: Path) -> Path:
        if source == first:
            raise OSError("copy failed")
        return real_copy(source, destination)

    monkeypatch.setattr(export_research_grade, "copy_file_preserving_metadata", flaky_copy)

    result = run(
        ExportResearchGradeInput(
            session_path=session_path,
            output=tmp_path / "custom-export",
        )
    )

    assert result.files_export_candidates == 2
    assert result.files_exported == 1
    assert result.files_failed == 1
    assert (tmp_path / "custom-export" / second.name).exists()
    assert not (tmp_path / "custom-export" / first.name).exists()


def test_run_rejects_session_path_outside_sessions(make_image, tmp_path: Path):
    session_path = tmp_path / "not-sessions" / "20240628_120000__HNT001"
    animal_path = session_path / "detection" / "animal"
    animal_path.mkdir(parents=True)
    make_image(
        animal_path / "animal.jpg",
        exif={"ImageDescription": "Research_Grade=true;"},
    )

    with pytest.raises(ValueError, match="sessions directory"):
        run(ExportResearchGradeInput(session_path=session_path))
