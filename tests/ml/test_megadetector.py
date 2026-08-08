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
        self.batch_thresholds: list[float] = []
        self.one_image_calls: list[str] = []
        self.one_image_thresholds: list[float] = []

    def generate_detections_one_batch(self, images, image_id, detection_threshold):
        self.batch_calls += 1
        self.batch_thresholds.append(detection_threshold)
        if self.fail_batch:
            raise RuntimeError("batch failed")

        return [self.batch_results[file_path] for file_path in image_id]

    def generate_detections_one_image(self, image, image_id, detection_threshold):
        self.one_image_calls.append(image_id)
        self.one_image_thresholds.append(detection_threshold)
        return self.per_image_results[image_id]


class FakeCompactPtDetector:
    def __init__(self, batch_results: dict[str, object]):
        self.batch_results = batch_results
        self.batch_inputs: list[dict[str, object]] = []

    def preprocess_image(self, image, image_id, image_size):
        assert image_size is None
        return {
            "file": image_id,
            "img_processed": object(),
            "img_original": type("Original", (), {"shape": (4000, 3000, 3)})(),
            "img_original_pil": image,
            "scaling_shape": (4000, 3000, 3),
            "letterbox_pad": (0, 0),
        }

    def generate_detections_one_batch(self, images, image_id, detection_threshold):
        import torch

        assert torch.is_inference_mode_enabled()
        assert image_id is None
        self.batch_inputs = images
        return [self.batch_results[image["file"]] for image in images]


FakeCompactPtDetector.__module__ = "megadetector.detection.pytorch_detector"


class FakeUnsupportedCompactPtDetector:
    def __init__(self, batch_results: dict[str, object]):
        self.batch_results = batch_results
        self.generic_image_ids: list[str] | None = None

    def preprocess_image(self, image, image_id, image_size):
        return {}

    def generate_detections_one_batch(self, images, image_id, detection_threshold):
        self.generic_image_ids = image_id
        return [self.batch_results[file_path] for file_path in image_id]


FakeUnsupportedCompactPtDetector.__module__ = "megadetector.detection.pytorch_detector"


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


def test_evaluate_images_normalizes_and_preserves_detections_for_routing(
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
        confidence_threshold=0.8,
        batch_size=8,
    )

    assert detector.batch_thresholds == [0.01]
    assert results[0].failure is None
    assert results[0].detections == [
        megadetector.MlDetection(label="animal", confidence=0.91),
        megadetector.MlDetection(label="animal", confidence=0.05),
    ]
    assert results[1].failure is None
    assert results[1].detections == [
        megadetector.MlDetection(label="other", confidence=0.83)
    ]


def test_evaluate_images_compacts_pytorch_preprocessing_before_batch_inference(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    image_path = make_image(tmp_path / "image.jpg")
    detector = FakeCompactPtDetector(
        {str(image_path): _raw_result(image_path, [{"category": "1", "conf": 0.91}])}
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images("MDV5A", [image_path], 0.8, 1)

    assert results[0].detections == [megadetector.MlDetection("animal", 0.91)]
    assert len(detector.batch_inputs) == 1
    compact_input = detector.batch_inputs[0]
    assert "img_original_pil" not in compact_input
    assert compact_input["img_original"].shape == (4000, 3000, 3)


def test_evaluate_images_falls_back_when_pytorch_preprocessing_schema_is_unknown(
    make_image,
    tmp_path: Path,
    monkeypatch,
):
    image_path = make_image(tmp_path / "image.jpg")
    detector = FakeUnsupportedCompactPtDetector(
        {str(image_path): _raw_result(image_path, [])}
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images("MDV5A", [image_path], 0.8, 1)

    assert results[0].failure is None
    assert detector.generic_image_ids == [str(image_path)]


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
        confidence_threshold=0.8,
        batch_size=8,
    )

    assert detector.batch_calls == 1
    assert detector.batch_thresholds == [0.01]
    assert detector.one_image_calls == [str(image_path)]
    assert detector.one_image_thresholds == [0.01]
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
        confidence_threshold=0.8,
        batch_size=8,
    )

    assert results == [
        megadetector.MlImageResult(
            file_path=image_path,
            detections=[],
            failure="Invalid detections payload.",
        )
    ]


def test_evaluate_images_preserves_batch_order_when_an_image_cannot_load(
    make_corrupted_image, make_image, tmp_path: Path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    first = make_image(source / "first.jpg")
    broken = make_corrupted_image(source / "broken.jpg")
    last = make_image(source / "last.jpg")
    detector = FakeBatchDetector(
        batch_results={
            str(first): _raw_result(first, [{"category": "1", "conf": 0.91}]),
            str(last): _raw_result(last, [{"category": "1", "conf": 0.92}]),
        }
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    results = megadetector.evaluate_images("MDV5A", [first, broken, last], 0.8, 8)

    assert [result.file_path for result in results] == [first, broken, last]
    assert results[1].failure is not None


def test_evaluate_images_rejects_non_finite_confidence(
    make_image, tmp_path: Path, monkeypatch
):
    image_path = make_image(tmp_path / "image.jpg")
    detector = FakeBatchDetector(
        batch_results={
            str(image_path): _raw_result(image_path, [{"category": "1", "conf": float("nan")}])
        }
    )
    monkeypatch.setattr(megadetector, "_load_detector", lambda model, force_download=False: detector)

    result = megadetector.evaluate_images("MDV5A", [image_path], 0.8, 1)[0]

    assert result.failure == "Invalid detection confidence."
