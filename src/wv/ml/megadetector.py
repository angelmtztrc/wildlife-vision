from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from PIL import Image, ImageOps

from wv.core.logger import capture_external_output, get_logger, get_progress
from wv.core.files import get_content_digest

DEFAULT_MODEL = "MDV5A"
_CATEGORY_LABELS = {1: "animal", 2: "human", 3: "vehicle"}
_MIN_DETECTION_THRESHOLD = 0.01

logger = get_logger(__name__)


@dataclass(frozen=True)
class PreparedModel:
    model: str
    resolved_model: Path
    inference_device: str


@dataclass(frozen=True)
class ResolvedModel:
    requested_model: str
    resolved_path: Path
    content_digest: str
    content_size_bytes: int


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

    with capture_external_output(logger, "MegaDetector load_detector"):
        return md_load_detector(model, force_model_download=force_download)


def _resolve_model_file(model: str, *, force_download: bool = False) -> Path:
    from megadetector.detection.run_detector import (
        try_download_known_detector as md_try_download_known_detector,
    )

    with capture_external_output(logger, "MegaDetector try_download_known_detector"):
        return Path(
            md_try_download_known_detector(model, force_download=force_download)
        )


def resolve_model(model: str) -> ResolvedModel:
    """Resolve and fingerprint the local MegaDetector model used for inference."""
    resolved_path = _resolve_model_file(model).resolve()
    return ResolvedModel(
        requested_model=model,
        resolved_path=resolved_path,
        content_digest=get_content_digest(resolved_path),
        content_size_bytes=resolved_path.stat().st_size,
    )


def _is_gpu_available(model_file: str) -> bool:
    from megadetector.detection.run_detector import is_gpu_available as md_is_gpu_available

    with capture_external_output(logger, "MegaDetector is_gpu_available"):
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
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("Invalid detection confidence.")

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

    file_path = default_file_path or Path(str(raw_result.get("file") or ""))

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
        with capture_external_output(logger, "MegaDetector generate_detections_one_image"):
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
    results: list[MlImageResult | None] = [None] * len(batch)
    loaded: list[tuple[int, Path, Image.Image]] = []

    for index, file_path in enumerate(batch):
        try:
            loaded.append((index, file_path, _load_image_for_detection(file_path)))
        except Exception as exc:
            results[index] = _failed_image_result(file_path, str(exc))

    if not loaded:
        return [result for result in results if result is not None]

    with capture_external_output(logger, "MegaDetector generate_detections_one_batch"):
        raw_results = detector.generate_detections_one_batch(
            [image for _, _, image in loaded],
            image_id=[str(file_path) for _, file_path, _ in loaded],
            detection_threshold=_MIN_DETECTION_THRESHOLD,
        )

    for (index, file_path, _), raw_result in zip(loaded, raw_results, strict=True):
        results[index] = _normalize_raw_result(
            raw_result,
            default_file_path=file_path,
        )
    return [result for result in results if result is not None]


def evaluate_images(
    model: str,
    image_paths: list[Path],
    confidence_threshold: float,
    batch_size: int,
) -> list[MlImageResult]:
    if not image_paths:
        return []

    detector = _load_detector(model)
    image_results: list[MlImageResult] = []
    supports_batch_inference = hasattr(detector, "generate_detections_one_batch")

    logger.info(
        "Starting MegaDetector evaluation for %s images (model=%s, batch_size=%s)",
        len(image_paths),
        model,
        batch_size,
    )
    logger.info("Evaluating images with MegaDetector")

    with get_progress() as progress:
        process = progress.add_task(
            "Evaluating images with MegaDetector", total=len(image_paths)
        )

        for batch in _chunk_paths(image_paths, batch_size):
            if supports_batch_inference:
                try:
                    batch_results = _run_detector_batch(detector, batch)
                    image_results.extend(batch_results)
                    progress.update(process, advance=len(batch_results))
                    continue
                except Exception:
                    logger.debug(
                        "Batch inference failed for %s images; falling back to per-image inference",
                        len(batch),
                    )

            for file_path in batch:
                image_results.append(_run_detector_one_image(detector, file_path))
                progress.update(process, advance=1)

    return image_results
