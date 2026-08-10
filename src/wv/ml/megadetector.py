from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from math import isfinite
from pathlib import Path

from PIL import Image, ImageOps

from wv.core.logger import capture_external_output, get_logger, get_progress
from wv.core.files import get_content_digest

DEFAULT_MODEL = "MDV5A"
_CATEGORY_LABELS = {1: "animal", 2: "human", 3: "vehicle"}
_MIN_DETECTION_THRESHOLD = 0.005

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
    bbox_x: float = 0.0
    bbox_y: float = 0.0
    bbox_width: float = 0.0
    bbox_height: float = 0.0


@dataclass(frozen=True)
class MlImageResult:
    file_path: Path
    detections: list[MlDetection]
    failure: str | None = None


@dataclass(frozen=True)
class _ShapeOnlyImage:
    shape: tuple[int, ...]


class _UnsupportedCompactPreprocessing(Exception):
    pass


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


def _chunk_paths(paths: list[Path], batch_size: int) -> Iterator[list[Path]]:
    for index in range(0, len(paths), batch_size):
        yield paths[index : index + batch_size]


def _inference_context(detector):
    if detector.__class__.__module__.endswith("pytorch_detector"):
        import torch

        return torch.inference_mode()
    return nullcontext()


def _supports_compact_pt_preprocessing(detector) -> bool:
    try:
        detector_version = version("megadetector")
    except PackageNotFoundError:
        return False
    return (
        detector_version == "10.0.23"
        and detector.__class__.__module__ == "megadetector.detection.pytorch_detector"
        and hasattr(detector, "preprocess_image")
    )


def _compact_preprocessed_image(image_info: object) -> dict[str, object]:
    if not isinstance(image_info, dict):
        raise _UnsupportedCompactPreprocessing(
            "Unexpected MegaDetector preprocessing result."
        )

    required_keys = {
        "file",
        "img_processed",
        "img_original",
        "scaling_shape",
        "letterbox_pad",
    }
    if not required_keys.issubset(image_info):
        raise _UnsupportedCompactPreprocessing(
            "Unexpected MegaDetector preprocessing result."
        )

    original_shape = getattr(image_info["img_original"], "shape", None)
    if not isinstance(original_shape, tuple):
        raise _UnsupportedCompactPreprocessing(
            "Unexpected MegaDetector original image shape."
        )

    compact = dict(image_info)
    compact.pop("img_original_pil", None)
    compact["img_original"] = _ShapeOnlyImage(original_shape)
    return compact


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

    bbox = raw_detection.get("bbox")
    if bbox is None:
        bbox = [0.0, 0.0, 0.0, 0.0]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("Invalid detection bounding box.")
    try:
        bbox_x, bbox_y, bbox_width, bbox_height = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid detection bounding box.") from exc
    if not all(isfinite(value) and 0.0 <= value <= 1.0 for value in (bbox_x, bbox_y, bbox_width, bbox_height)):
        raise ValueError("Invalid detection bounding box.")
    if bbox_x + bbox_width > 1.0 or bbox_y + bbox_height > 1.0:
        raise ValueError("Invalid detection bounding box.")

    try:
        category_id = int(str(raw_detection.get("category")))
    except (TypeError, ValueError):
        category_id = -1

    return MlDetection(
        label=_CATEGORY_LABELS.get(category_id, "other"),
        confidence=confidence,
        bbox_x=bbox_x,
        bbox_y=bbox_y,
        bbox_width=bbox_width,
        bbox_height=bbox_height,
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
        with _inference_context(detector):
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


def _run_generic_detector_batch(
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

    with _inference_context(detector):
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


def _run_compact_pt_detector_batch(detector, batch: list[Path]) -> list[MlImageResult]:
    results: list[MlImageResult | None] = [None] * len(batch)
    prepared: list[tuple[int, Path, dict[str, object]]] = []

    for index, file_path in enumerate(batch):
        try:
            with Image.open(file_path) as image:
                ImageOps.exif_transpose(image, in_place=True)
                image_info = detector.preprocess_image(
                    image,
                    image_id=str(file_path),
                    image_size=None,
                )
            prepared.append((index, file_path, _compact_preprocessed_image(image_info)))
        except _UnsupportedCompactPreprocessing:
            raise
        except Exception as exc:
            results[index] = _failed_image_result(file_path, str(exc))

    if not prepared:
        return [result for result in results if result is not None]

    with _inference_context(detector):
        with capture_external_output(logger, "MegaDetector generate_detections_one_batch"):
            raw_results = detector.generate_detections_one_batch(
                [image_info for _, _, image_info in prepared],
                image_id=None,
                detection_threshold=_MIN_DETECTION_THRESHOLD,
            )

    for (index, file_path, _), raw_result in zip(prepared, raw_results, strict=True):
        results[index] = _normalize_raw_result(
            raw_result,
            default_file_path=file_path,
        )
    return [result for result in results if result is not None]


def _run_detector_batch(detector, batch: list[Path]) -> list[MlImageResult]:
    if _supports_compact_pt_preprocessing(detector):
        try:
            return _run_compact_pt_detector_batch(detector, batch)
        except _UnsupportedCompactPreprocessing:
            logger.debug("Falling back to generic MegaDetector preprocessing")
    return _run_generic_detector_batch(detector, batch)


def iter_evaluate_images(
    model: str,
    image_paths: list[Path],
    confidence_threshold: float,
    batch_size: int,
) -> Iterator[MlImageResult]:
    if not image_paths:
        return

    detector = _load_detector(model)
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
                    progress.update(process, advance=len(batch_results))
                    yield from batch_results
                    continue
                except Exception:
                    logger.debug(
                        "Batch inference failed for %s images; falling back to per-image inference",
                        len(batch),
                    )

            for file_path in batch:
                yield _run_detector_one_image(detector, file_path)
                progress.update(process, advance=1)


def evaluate_images(
    model: str,
    image_paths: list[Path],
    confidence_threshold: float,
    batch_size: int,
) -> list[MlImageResult]:
    return list(
        iter_evaluate_images(model, image_paths, confidence_threshold, batch_size)
    )
