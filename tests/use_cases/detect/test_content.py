from pathlib import Path

from wv.core.exif import read_exif
from wv.ml.megadetector import MlDetection, MlImageResult
from wv.use_cases.detect.content import DetectContentInput, run
import wv.use_cases.detect.content as content


def _result_for(file_path: Path, detections: list[MlDetection]) -> MlImageResult:
    return MlImageResult(file_path=file_path, detections=detections, failure=None)


def test_run_classifies_moves_and_writes_metadata(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    animal = make_image(
        source / "animal.jpg",
        exif={"ImageDescription": "Camera=HNT001;broken;"},
    )
    human = make_image(source / "human.jpg")
    vehicle = make_image(source / "vehicle.jpg")
    empty = make_image(source / "empty.jpg")
    other = make_image(source / "other.jpg")
    (source / "notes.txt").write_text("ignore me")

    monkeypatch.setattr(
        content,
        "evaluate_images",
        lambda model, image_paths, confidence_threshold, batch_size: [
            _result_for(animal, [MlDetection(label="animal", confidence=0.91)]),
            _result_for(human, [MlDetection(label="human", confidence=0.82)]),
            _result_for(vehicle, [MlDetection(label="vehicle", confidence=0.73)]),
            _result_for(empty, []),
            _result_for(
                other,
                [
                    MlDetection(label="animal", confidence=0.61),
                    MlDetection(label="human", confidence=0.94),
                ],
            ),
        ],
    )

    result = run(DetectContentInput(source=source, output=output, batch_size=8))

    assert result.destination == output / "detection"
    assert result.files_discovered == 6
    assert result.files_evaluated == 5
    assert result.files_moved == 5
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert result.files_animal == 1
    assert result.files_human == 1
    assert result.files_vehicle == 1
    assert result.files_empty == 1
    assert result.files_other == 1

    animal_destination = output / "detection" / "animal" / "animal.jpg"
    human_destination = output / "detection" / "human" / "human.jpg"
    vehicle_destination = output / "detection" / "vehicle" / "vehicle.jpg"
    empty_destination = output / "detection" / "empty" / "empty.jpg"
    other_destination = output / "detection" / "other" / "other.jpg"

    assert animal_destination.exists()
    assert human_destination.exists()
    assert vehicle_destination.exists()
    assert empty_destination.exists()
    assert other_destination.exists()

    assert read_exif(animal_destination, "ImageDescription") == (
        "Camera=HNT001;Detection=animal;Detection_Confidence=0.91;"
    )
    assert read_exif(empty_destination, "ImageDescription") == (
        "Detection=empty;Detection_Confidence=0;"
    )
    assert read_exif(other_destination, "ImageDescription") == (
        "Detection=other;Detection_Confidence=0.94;"
    )


def test_run_does_not_move_or_write_in_dry_run(make_image, tmp_path: Path, monkeypatch):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")

    monkeypatch.setattr(
        content,
        "evaluate_images",
        lambda model, image_paths, confidence_threshold, batch_size: [
            _result_for(image_path, [MlDetection(label="animal", confidence=0.91)])
        ],
    )

    result = run(DetectContentInput(source=source, output=output, dry_run=True))

    assert result.files_evaluated == 1
    assert result.files_moved == 0
    assert result.files_failed == 0
    assert image_path.exists()
    assert not (output / "detection").exists()
    assert read_exif(image_path, "ImageDescription") is None


def test_run_counts_metadata_write_failures_and_leaves_file_in_place(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")

    monkeypatch.setattr(
        content,
        "evaluate_images",
        lambda model, image_paths, confidence_threshold, batch_size: [
            _result_for(image_path, [MlDetection(label="animal", confidence=0.91)])
        ],
    )
    monkeypatch.setattr(
        content,
        "write_exif_image_description",
        lambda file_path, data: (_ for _ in ()).throw(OSError("metadata write failed")),
    )

    result = run(DetectContentInput(source=source, output=output))

    assert result.files_evaluated == 1
    assert result.files_failed == 1
    assert result.files_moved == 0
    assert image_path.exists()


def test_run_counts_replacements_when_destination_file_exists(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")
    destination = output / "detection" / "animal" / "animal.jpg"
    destination.parent.mkdir(parents=True)
    make_image(destination)

    monkeypatch.setattr(
        content,
        "evaluate_images",
        lambda model, image_paths, confidence_threshold, batch_size: [
            _result_for(image_path, [MlDetection(label="animal", confidence=0.91)])
        ],
    )

    result = run(DetectContentInput(source=source, output=output))

    assert result.files_moved == 1
    assert result.files_replaced == 1
    assert result.files_failed == 0
    assert destination.exists()
    assert not image_path.exists()
