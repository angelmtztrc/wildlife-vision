import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, is_allowed_image_file
from wv.core.metadata import upsert_image_description_properties
from wv.ml.megadetector import DEFAULT_MODEL, MlDetection, evaluate_images

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_AMBIGUITY_GAP = 0.3



@dataclass(frozen=True)
class DetectContentInput:
    source: Path
    output: Path
    model: str = DEFAULT_MODEL
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
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


def _classify_detections(
    detections: list[MlDetection], confidence_threshold: float
) -> DetectionDecision:
    if not detections:
        return DetectionDecision(label="empty", confidence=0.0)

    confidence_by_label: dict[str, float] = {}
    for detection in detections:
        confidence_by_label[detection.label] = max(
            confidence_by_label.get(detection.label, 0.0), detection.confidence
        )

    ranked_labels = sorted(
        confidence_by_label.items(), key=lambda item: item[1], reverse=True
    )
    best_label, best_confidence = ranked_labels[0]

    if best_confidence < confidence_threshold:
        return DetectionDecision(label="other", confidence=best_confidence)

    if (
        len(ranked_labels) > 1
        and best_confidence - ranked_labels[1][1] < DEFAULT_AMBIGUITY_GAP
    ):
        return DetectionDecision(label="other", confidence=best_confidence)

    return DetectionDecision(label=best_label, confidence=best_confidence)


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

    detection_results = evaluate_images(
        model=input_data.model,
        image_paths=image_paths,
        confidence_threshold=input_data.confidence_threshold,
        batch_size=input_data.batch_size,
    )

    for detection_result in detection_results:
        if detection_result.failure:
            result.files_failed += 1
            continue

        file_path = detection_result.file_path
        decision = _classify_detections(
            detection_result.detections, input_data.confidence_threshold
        )
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
