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
    low_confidence = make_image(source / "low-confidence.jpg")
    ambiguous = make_image(source / "ambiguous.jpg")
    human_wins = make_image(source / "human-wins.jpg")
    (source / "notes.txt").write_text("ignore me")

    monkeypatch.setattr(
        content,
        "evaluate_images",
        lambda model, image_paths, confidence_threshold, batch_size: [
            _result_for(animal, [MlDetection(label="animal", confidence=0.91)]),
            _result_for(human, [MlDetection(label="human", confidence=0.82)]),
            _result_for(vehicle, [MlDetection(label="vehicle", confidence=0.83)]),
            _result_for(empty, []),
            _result_for(
                low_confidence,
                [MlDetection(label="animal", confidence=0.60)],
            ),
            _result_for(
                ambiguous,
                [
                    MlDetection(label="animal", confidence=0.81),
                    MlDetection(label="human", confidence=0.61),
                ],
            ),
            _result_for(
                human_wins,
                [
                    MlDetection(label="animal", confidence=0.20),
                    MlDetection(label="human", confidence=0.83),
                ],
            ),
        ],
    )

    result = run(DetectContentInput(source=source, output=output, batch_size=8))

    assert result.destination == output / "detection"
    assert result.files_discovered == 8
    assert result.files_evaluated == 7
    assert result.files_moved == 7
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert result.files_animal == 1
    assert result.files_human == 2
    assert result.files_vehicle == 1
    assert result.files_empty == 1
    assert result.files_other == 2

    animal_destination = output / "detection" / "animal" / "animal.jpg"
    human_destination = output / "detection" / "human" / "human.jpg"
    vehicle_destination = output / "detection" / "vehicle" / "vehicle.jpg"
    empty_destination = output / "detection" / "empty" / "empty.jpg"
    low_confidence_destination = output / "detection" / "other" / "low-confidence.jpg"
    ambiguous_destination = output / "detection" / "other" / "ambiguous.jpg"
    human_wins_destination = output / "detection" / "human" / "human-wins.jpg"

    assert animal_destination.exists()
    assert human_destination.exists()
    assert vehicle_destination.exists()
    assert empty_destination.exists()
    assert low_confidence_destination.exists()
    assert ambiguous_destination.exists()
    assert human_wins_destination.exists()

    assert read_exif(animal_destination, "ImageDescription") == (
        "Camera=HNT001;Detection=animal;Detection_Confidence=0.91;"
    )
    assert read_exif(empty_destination, "ImageDescription") == (
        "Detection=empty;Detection_Confidence=0;"
    )
    assert read_exif(low_confidence_destination, "ImageDescription") == (
        "Detection=other;Detection_Confidence=0.6;"
    )
    assert read_exif(ambiguous_destination, "ImageDescription") == (
        "Detection=other;Detection_Confidence=0.81;"
    )
    assert read_exif(human_wins_destination, "ImageDescription") == (
        "Detection=human;Detection_Confidence=0.83;"
    )


def test_run_uses_highest_confidence_per_label_for_routing(
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
            _result_for(
                image_path,
                [
                    MlDetection(label="animal", confidence=0.82),
                    MlDetection(label="animal", confidence=0.54),
                    MlDetection(label="human", confidence=0.45),
                ],
            )
        ],
    )

    result = run(DetectContentInput(source=source, output=output))

    assert result.files_animal == 1
    assert result.files_other == 0
    destination = output / "detection" / "animal" / "animal.jpg"
    assert destination.exists()
    assert read_exif(destination, "ImageDescription") == (
        "Detection=animal;Detection_Confidence=0.82;"
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
