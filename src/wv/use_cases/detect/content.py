import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.megadetector import load_detector
from wv.core.metadata import upsert_image_description_properties

DEFAULT_MODEL = "MDV5A"
_CATEGORY_LABELS = {1: "animal", 2: "human", 3: "vehicle"}


@dataclass(frozen=True)
class DetectContentInput:
    source: Path
    output: Path
    model: str = DEFAULT_MODEL
    confidence_threshold: float = 0.2
    batch_size: int = 32
    dry_run: bool = False


@dataclass
class DetectContentResult:
    files_discovered: int = 0
    files_evaluated: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    files_animal: int = 0
    files_human: int = 0
    files_vehicle: int = 0
    files_empty: int = 0
    files_other: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass(frozen=True)
class DetectionDecision:
    label: str
    confidence: float


def _chunk_paths(paths: list[Path], batch_size: int) -> list[list[Path]]:
    return [paths[index : index + batch_size] for index in range(0, len(paths), batch_size)]


def _failed_detection_result(file_path: Path, failure: str) -> dict[str, object]:
    return {
        "file": str(file_path),
        "failure": failure,
        "detections": [],
    }


def _load_image_for_detection(file_path: Path) -> Image.Image:
    with Image.open(file_path) as image:
        return ImageOps.exif_transpose(image).copy()


def _run_detector_one_image(
    detector, file_path: Path, confidence_threshold: float
) -> dict[str, object]:
    try:
        image = _load_image_for_detection(file_path)
        return detector.generate_detections_one_image(
            image,
            image_id=str(file_path),
            detection_threshold=confidence_threshold,
        )
    except Exception as exc:
        return _failed_detection_result(file_path, str(exc))


def _run_detector_batch(
    detector, batch: list[Path], confidence_threshold: float
) -> list[dict[str, object]]:
    loaded_images: list[Image.Image] = []
    loaded_paths: list[Path] = []
    detection_results: list[dict[str, object]] = []

    for file_path in batch:
        try:
            loaded_images.append(_load_image_for_detection(file_path))
            loaded_paths.append(file_path)
        except Exception as exc:
            detection_results.append(_failed_detection_result(file_path, str(exc)))

    if not loaded_images:
        return detection_results

    batch_results = detector.generate_detections_one_batch(
        loaded_images,
        image_id=[str(file_path) for file_path in loaded_paths],
        detection_threshold=confidence_threshold,
    )

    return detection_results + batch_results


def _evaluate_images(
    detector, image_paths: list[Path], confidence_threshold: float, batch_size: int
) -> list[dict[str, object]]:
    detection_results: list[dict[str, object]] = []
    supports_batch_inference = hasattr(detector, "generate_detections_one_batch")

    for batch in _chunk_paths(image_paths, batch_size):
        if supports_batch_inference:
            try:
                detection_results.extend(
                    _run_detector_batch(detector, batch, confidence_threshold)
                )
                continue
            except Exception:
                pass

        for file_path in batch:
            detection_results.append(
                _run_detector_one_image(detector, file_path, confidence_threshold)
            )

    return detection_results


def _get_detection_confidence(detection: dict[str, object]) -> float:
    try:
        return float(detection.get("conf", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _get_detection_label(detection: dict[str, object]) -> str | None:
    category = detection.get("category")

    try:
        category_id = int(str(category))
    except (TypeError, ValueError):
        return None

    return _CATEGORY_LABELS.get(category_id)


def _classify_detections(
    detections: list[dict[str, object]], confidence_threshold: float
) -> DetectionDecision:
    labels: set[str] = set()
    max_confidence = 0.0

    for detection in detections:
        confidence = _get_detection_confidence(detection)
        if confidence < confidence_threshold:
            continue

        label = _get_detection_label(detection)
        labels.add(label or "other")
        max_confidence = max(max_confidence, confidence)

    if not labels:
        return DetectionDecision(label="empty", confidence=0.0)

    if len(labels) == 1:
        return DetectionDecision(label=next(iter(labels)), confidence=max_confidence)

    return DetectionDecision(label="other", confidence=max_confidence)


def _increment_decision_counter(
    result: DetectContentResult, decision: DetectionDecision
) -> None:
    if decision.label == "animal":
        result.files_animal += 1
    elif decision.label == "human":
        result.files_human += 1
    elif decision.label == "vehicle":
        result.files_vehicle += 1
    elif decision.label == "empty":
        result.files_empty += 1
    else:
        result.files_other += 1


def _format_detection_confidence(confidence: float) -> str:
    return f"{confidence:.6f}".rstrip("0").rstrip(".") or "0"


def _read_existing_image_description(file_path: Path) -> str | None:
    value = read_exif(file_path, "ImageDescription")
    if value is None:
        return None

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")

    return str(value)


def _move_source_to_destination(source: Path, destination: Path) -> tuple[bool, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)

    replaced_existing = destination.exists()
    temp_destination = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

    try:
        shutil.move(str(source), temp_destination)
        temp_destination.replace(destination)
        return True, replaced_existing
    finally:
        if temp_destination.exists():
            temp_destination.unlink()


def run(input_data: DetectContentInput) -> DetectContentResult:
    if not 0.0 <= input_data.confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.0 and 1.0.")

    if input_data.batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    destination_root = input_data.output / "detection"
    result = DetectContentResult(destination=destination_root, dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())
    result.files_discovered = len(source_files)

    image_paths: list[Path] = []

    for file_path in source_files:
        if not file_path.is_file() or not is_allowed_image_file(file_path):
            result.files_ignored += 1
            continue

        if file_path.is_relative_to(destination_root):
            result.files_ignored += 1
            continue

        image_paths.append(file_path)

    detector = load_detector(input_data.model)
    detection_results = _evaluate_images(
        detector=detector,
        image_paths=image_paths,
        confidence_threshold=input_data.confidence_threshold,
        batch_size=input_data.batch_size,
    )

    for detection_result in detection_results:
        file_path = Path(str(detection_result.get("file", "")))
        failure = detection_result.get("failure")
        if failure:
            result.files_failed += 1
            continue

        detections = detection_result.get("detections", [])
        if not isinstance(detections, list):
            result.files_failed += 1
            continue

        decision = _classify_detections(detections, input_data.confidence_threshold)
        result.files_evaluated += 1
        _increment_decision_counter(result, decision)

        if input_data.dry_run:
            continue

        try:
            updated_description = upsert_image_description_properties(
                _read_existing_image_description(file_path),
                {
                    "Detection": decision.label,
                    "Detection_Confidence": _format_detection_confidence(
                        decision.confidence
                    ),
                },
            )
            write_exif_image_description(file_path, updated_description)

            moved, replaced_existing = _move_source_to_destination(
                source=file_path,
                destination=destination_root / decision.label / file_path.name,
            )
            if moved:
                result.files_moved += 1
            if replaced_existing:
                result.files_replaced += 1
        except Exception:
            result.files_failed += 1

    return result
