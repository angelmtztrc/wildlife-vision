from pathlib import Path

import wv.ml.megadetector as megadetector


class FakeCudaDetector:
    device = "cuda:0"


class FakeCpuDetector:
    device = "cpu"


class FakeBatchDetector:
    def __init__(
        self,
        batch_results: dict[str, object] | None = None,
        per_image_results: dict[str, object] | None = None,
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


def _raw_result(file_path: Path, detections: list[dict[str, object]]) -> dict[str, object]:
    return {
        "file": str(file_path),
        "failure": None,
        "detections": detections,
    }


def test_prepare_model_reports_gpu_when_detector_device_uses_gpu(monkeypatch):
    monkeypatch.setattr(
        megadetector,
        "_load_detector",
        lambda model, force_download=False: FakeCudaDetector(),
    )
    monkeypatch.setattr(
        megadetector,
        "_resolve_model_file",
        lambda model, force_download=False: Path("/tmp/md_v5a.0.1.pt"),
    )

    prepared = megadetector.prepare_model()

    assert prepared.model == "MDV5A"
    assert prepared.resolved_model == Path("/tmp/md_v5a.0.1.pt")
    assert prepared.inference_device == "GPU"


def test_prepare_model_falls_back_to_cpu_when_gpu_is_not_available(monkeypatch):
    monkeypatch.setattr(
        megadetector,
        "_load_detector",
        lambda model, force_download=False: FakeCpuDetector(),
    )
    monkeypatch.setattr(
        megadetector,
        "_resolve_model_file",
        lambda model, force_download=False: Path("/tmp/md_v5a.0.1.pt"),
    )
    monkeypatch.setattr(megadetector, "_is_gpu_available", lambda model_file: False)

    prepared = megadetector.prepare_model()

    assert prepared.inference_device == "CPU"


def test_evaluate_images_normalizes_and_filters_detections(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    source.mkdir()
    animal = make_image(source / "animal.jpg")
    other = make_image(source / "other.jpg")

    detector = FakeBatchDetector(
        batch_results={
            str(animal): _raw_result(
                animal,
                [
                    {"category": "1", "conf": 0.91},
                    {"category": "1", "conf": 0.05},
                ],
            ),
            str(other): _raw_result(other, [{"category": "99", "conf": 0.83}]),
        }
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images(
        model="MDV5A",
        image_paths=[animal, other],
        confidence_threshold=0.2,
        batch_size=8,
    )

    assert results[0].failure is None
    assert results[0].detections == [
        megadetector.MlDetection(label="animal", confidence=0.91)
    ]
    assert results[1].failure is None
    assert results[1].detections == [
        megadetector.MlDetection(label="other", confidence=0.83)
    ]


def test_evaluate_images_falls_back_to_per_image_inference_when_batch_fails(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")

    detector = FakeBatchDetector(
        per_image_results={
            str(image_path): _raw_result(image_path, [{"category": "1", "conf": 0.91}])
        },
        fail_batch=True,
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images(
        model="MDV5A",
        image_paths=[image_path],
        confidence_threshold=0.2,
        batch_size=8,
    )

    assert detector.batch_calls == 1
    assert detector.one_image_calls == [str(image_path)]
    assert results == [
        megadetector.MlImageResult(
            file_path=image_path,
            detections=[megadetector.MlDetection(label="animal", confidence=0.91)],
            failure=None,
        )
    ]


def test_evaluate_images_marks_invalid_detection_payload_as_failure(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "animal.jpg")

    detector = FakeBatchDetector(
        batch_results={
            str(image_path): {
                "file": str(image_path),
                "failure": None,
                "detections": "not-a-list",
            }
        }
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images(
        model="MDV5A",
        image_paths=[image_path],
        confidence_threshold=0.2,
        batch_size=8,
    )

    assert results == [
        megadetector.MlImageResult(
            file_path=image_path,
            detections=[],
            failure="Invalid detections payload.",
        )
    ]
