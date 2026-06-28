from pathlib import Path

from wv.core.exif import read_exif
from wv.use_cases.detect.content import DetectContentInput, run
import wv.use_cases.detect.content as content


def _result_for(file_path: Path, detections: list[dict[str, object]]) -> dict[str, object]:
    return {
        "file": str(file_path),
        "failure": None,
        "detections": detections,
    }


class FakeBatchDetector:
    def __init__(
        self,
        batch_results: dict[str, dict[str, object]] | None = None,
        per_image_results: dict[str, dict[str, object]] | None = None,
        fail_batch: bool = False,
    ):
        self.batch_results = batch_results or {}
        self.per_image_results = per_image_results or {}
        self.fail_batch = fail_batch
        self.batch_calls = 0
        self.one_image_calls: list[str] = []

    def generate_detections_one_batch(self, images, image_id, detection_threshold):
        self.batch_calls += 1
        if self.fail_batch:
            raise RuntimeError("batch failed")

        return [self.batch_results[file_path] for file_path in image_id]

    def generate_detections_one_image(self, image, image_id, detection_threshold):
        self.one_image_calls.append(image_id)
        return self.per_image_results[image_id]


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

    detector = FakeBatchDetector(
        batch_results={
            str(animal): _result_for(animal, [{"category": "1", "conf": 0.91}]),
            str(human): _result_for(human, [{"category": "2", "conf": 0.82}]),
            str(vehicle): _result_for(vehicle, [{"category": "3", "conf": 0.73}]),
            str(empty): _result_for(empty, [{"category": "1", "conf": 0.05}]),
            str(other): _result_for(
                other,
                [
                    {"category": "1", "conf": 0.61},
                    {"category": "2", "conf": 0.94},
                ],
            ),
        }
    )
    monkeypatch.setattr(content, "load_detector", lambda model: detector)

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

    detector = FakeBatchDetector(
        batch_results={
            str(image_path): _result_for(image_path, [{"category": "1", "conf": 0.91}])
        }
    )
    monkeypatch.setattr(content, "load_detector", lambda model: detector)

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

    detector = FakeBatchDetector(
        batch_results={
            str(image_path): _result_for(image_path, [{"category": "1", "conf": 0.91}])
        }
    )
    monkeypatch.setattr(content, "load_detector", lambda model: detector)
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

    detector = FakeBatchDetector(
        batch_results={
            str(image_path): _result_for(image_path, [{"category": "1", "conf": 0.91}])
        }
    )
    monkeypatch.setattr(content, "load_detector", lambda model: detector)

    result = run(DetectContentInput(source=source, output=output))

    assert result.files_moved == 1
    assert result.files_replaced == 1
    assert result.files_failed == 0
    assert destination.exists()
    assert not image_path.exists()


def test_run_falls_back_to_per_image_inference_when_batch_call_fails(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")

    detector = FakeBatchDetector(
        per_image_results={
            str(image_path): _result_for(image_path, [{"category": "1", "conf": 0.91}])
        },
        fail_batch=True,
    )
    monkeypatch.setattr(content, "load_detector", lambda model: detector)

    result = run(DetectContentInput(source=source, output=output, dry_run=True))

    assert detector.batch_calls == 1
    assert detector.one_image_calls == [str(image_path)]
    assert result.files_evaluated == 1
    assert result.files_failed == 0
