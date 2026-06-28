from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

DEFAULT_MODEL = "MDV5A"
_CATEGORY_LABELS = {1: "animal", 2: "human", 3: "vehicle"}
_MIN_DETECTION_THRESHOLD = 0.01


@dataclass(frozen=True)
class PreparedModel:
    model: str
    resolved_model: Path
    inference_device: str


@dataclass(frozen=True)
class MlDetection:
    label: str
    confidence: float


@dataclass(frozen=True)
class MlImageResult:
    file_path: Path
    detections: list[MlDetection]
    failure: str | None = None


def _load_detector(model: str, *, force_download: bool = False):
    from megadetector.detection.run_detector import load_detector as md_load_detector

    return md_load_detector(model, force_model_download=force_download)


def _resolve_model_file(model: str, *, force_download: bool = False) -> Path:
    from megadetector.detection.run_detector import (
        try_download_known_detector as md_try_download_known_detector,
    )

    return Path(md_try_download_known_detector(model, force_download=force_download))


def _is_gpu_available(model_file: str) -> bool:
    from megadetector.detection.run_detector import is_gpu_available as md_is_gpu_available

    return bool(md_is_gpu_available(model_file))


def _get_inference_device(detector, resolved_model: Path) -> str:
    detector_device = getattr(detector, "device", None)
    if detector_device is not None:
        normalized_device = str(detector_device).lower()
        if any(device_name in normalized_device for device_name in ("cuda", "mps", "directml")):
            return "GPU"

    return "GPU" if _is_gpu_available(str(resolved_model)) else "CPU"


def prepare_model(
    model: str = DEFAULT_MODEL, force_download: bool = False
) -> PreparedModel:
    detector = _load_detector(model, force_download=force_download)
    resolved_model = _resolve_model_file(model, force_download=False)

    return PreparedModel(
        model=model,
        resolved_model=resolved_model,
        inference_device=_get_inference_device(detector, resolved_model),
    )


def _chunk_paths(paths: list[Path], batch_size: int) -> list[list[Path]]:
    return [paths[index : index + batch_size] for index in range(0, len(paths), batch_size)]


def _failed_image_result(file_path: Path, failure: str) -> MlImageResult:
    return MlImageResult(file_path=file_path, detections=[], failure=failure)


def _load_image_for_detection(file_path: Path) -> Image.Image:
    with Image.open(file_path) as image:
        return ImageOps.exif_transpose(image).copy()


def _normalize_detection(raw_detection: dict[str, object]) -> MlDetection:
    if not isinstance(raw_detection, dict):
        raise TypeError("Invalid detection payload.")

    try:
        confidence = float(raw_detection.get("conf", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid detection confidence.") from exc

    try:
        category_id = int(str(raw_detection.get("category")))
    except (TypeError, ValueError):
        category_id = -1

    return MlDetection(
        label=_CATEGORY_LABELS.get(category_id, "other"),
        confidence=confidence,
    )


def _normalize_raw_result(
    raw_result: object,
    *,
    default_file_path: Path | None = None,
) -> MlImageResult:
    if not isinstance(raw_result, dict):
        return _failed_image_result(
            default_file_path or Path(),
            "Invalid detector result payload.",
        )

    file_value = raw_result.get("file")
    file_path = Path(str(file_value)) if file_value else (default_file_path or Path())

    failure = raw_result.get("failure")
    if failure:
        return _failed_image_result(file_path, str(failure))

    raw_detections = raw_result.get("detections", [])
    if not isinstance(raw_detections, list):
        return _failed_image_result(file_path, "Invalid detections payload.")

    try:
        detections = [
            _normalize_detection(raw_detection) for raw_detection in raw_detections
        ]
    except Exception as exc:
        return _failed_image_result(file_path, str(exc))

    return MlImageResult(file_path=file_path, detections=detections)


def _run_detector_one_image(
    detector, file_path: Path
) -> MlImageResult:
    try:
        image = _load_image_for_detection(file_path)
        raw_result = detector.generate_detections_one_image(
            image,
            image_id=str(file_path),
            detection_threshold=_MIN_DETECTION_THRESHOLD,
        )
        return _normalize_raw_result(
            raw_result,
            default_file_path=file_path,
        )
    except Exception as exc:
        return _failed_image_result(file_path, str(exc))


def _run_detector_batch(
    detector, batch: list[Path]
) -> list[MlImageResult]:
    loaded_images: list[Image.Image] = []
    loaded_paths: list[Path] = []
    image_results: list[MlImageResult] = []

    for file_path in batch:
        try:
            loaded_images.append(_load_image_for_detection(file_path))
            loaded_paths.append(file_path)
        except Exception as exc:
            image_results.append(_failed_image_result(file_path, str(exc)))

    if not loaded_images:
        return image_results

    raw_results = detector.generate_detections_one_batch(
        loaded_images,
        image_id=[str(file_path) for file_path in loaded_paths],
        detection_threshold=_MIN_DETECTION_THRESHOLD,
    )

    for file_path, raw_result in zip(loaded_paths, raw_results, strict=True):
        image_results.append(
            _normalize_raw_result(
                raw_result,
                default_file_path=file_path,
            )
        )

    return image_results


def evaluate_images(
    model: str,
    image_paths: list[Path],
    confidence_threshold: float,
    batch_size: int,
) -> list[MlImageResult]:
    detector = _load_detector(model)
    image_results: list[MlImageResult] = []
    supports_batch_inference = hasattr(detector, "generate_detections_one_batch")

    for batch in _chunk_paths(image_paths, batch_size):
        if supports_batch_inference:
            try:
                image_results.extend(_run_detector_batch(detector, batch))
                continue
            except Exception:
                pass

        for file_path in batch:
            image_results.append(_run_detector_one_image(detector, file_path))

    return image_results
