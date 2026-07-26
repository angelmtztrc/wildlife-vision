from dataclasses import dataclass
from pathlib import Path

from wv.core.display import display_file, display_path
from wv.core.exif import read_exif, write_exif_image_description
from wv.core.files import ensure_directory, is_allowed_image_file, move_file_with_staged_copy
from wv.core.logger import get_logger, get_progress
from wv.core.metadata import upsert_image_description_properties
from wv.core.session import get_detection_path
from wv.ml.megadetector import DEFAULT_MODEL, MlDetection, evaluate_images

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_AMBIGUITY_GAP = 0.3

logger = get_logger(__name__)



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


def run(input_data: DetectContentInput) -> DetectContentResult:
    if not 0.0 <= input_data.confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.0 and 1.0.")

    if input_data.batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    destination_root = get_detection_path(input_data.output)
    result = DetectContentResult(destination=destination_root, dry_run=input_data.dry_run)

    ensure_directory(input_data.source)

    source_files = list(input_data.source.iterdir())
    result.files_discovered = len(source_files)

    image_paths: list[Path] = []

    logger.info(
        "Discovered %s entries for content detection; destination is %s (model=%s, confidence_threshold=%s, batch_size=%s, dry_run=%s)",
        result.files_discovered,
        display_path(destination_root),
        input_data.model,
        input_data.confidence_threshold,
        input_data.batch_size,
        input_data.dry_run,
    )
    logger.info("Scanning detection candidates")

    with get_progress() as progress:
        process = progress.add_task(
            "Scanning detection candidates", total=result.files_discovered
        )

        for file_path in source_files:
            if not file_path.is_file() or not is_allowed_image_file(file_path):
                result.files_ignored += 1
                logger.debug(
                    "Skipping %s: not a supported image file", display_file(file_path)
                )
                progress.update(process, advance=1)
                continue

            if file_path.is_relative_to(destination_root):
                result.files_ignored += 1
                logger.debug(
                    "Skipping %s: already under detection output root",
                    display_file(file_path),
                )
                progress.update(process, advance=1)
                continue

            image_paths.append(file_path)
            progress.update(process, advance=1)

    logger.info(
        "Prepared %s image candidates for MegaDetector evaluation",
        len(image_paths),
    )

    detection_results = evaluate_images(
        model=input_data.model,
        image_paths=image_paths,
        confidence_threshold=input_data.confidence_threshold,
        batch_size=input_data.batch_size,
    )

    logger.info(
        "MegaDetector returned %s detection results; starting post-processing",
        len(detection_results),
    )
    logger.info("Applying detection decisions")

    with get_progress() as progress:
        process = progress.add_task(
            "Applying detection decisions", total=len(detection_results)
        )

        for detection_result in detection_results:
            if detection_result.failure:
                result.files_failed += 1
                logger.error(
                    "Detection failed for %s: %s",
                    display_file(detection_result.file_path),
                    detection_result.failure,
                )
                progress.update(process, advance=1)
                continue

            file_path = detection_result.file_path
            decision = _classify_detections(
                detection_result.detections, input_data.confidence_threshold
            )
            result.files_evaluated += 1
            _increment_decision_counter(result, decision)

            logger.debug(
                "Classified %s as %s (confidence=%s)",
                display_file(file_path),
                decision.label,
                _format_detection_confidence(decision.confidence),
            )

            if input_data.dry_run:
                logger.debug(
                    "Dry run: would move %s to %s",
                    display_file(file_path),
                    display_file(get_detection_path(input_data.output, decision.label) / file_path.name),
                )
                progress.update(process, advance=1)
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
                destination = get_detection_path(input_data.output, decision.label) / file_path.name

                def _write_detection_metadata(staged_file: Path) -> None:
                    write_exif_image_description(staged_file, updated_description)

                moved, replaced_existing = move_file_with_staged_copy(
                    source=file_path,
                    destination=destination,
                    transform=_write_detection_metadata,
                )
                if moved:
                    result.files_moved += 1
                    logger.debug(
                        "Moved %s to %s",
                        display_file(file_path),
                        display_file(destination),
                    )
                if replaced_existing:
                    result.files_replaced += 1
                    logger.debug(
                        "Replaced existing detection destination at %s",
                        display_file(destination),
                    )
            except Exception:
                result.files_failed += 1
                logger.exception(
                    "Failed to apply detection decision for %s",
                    display_file(file_path),
                )

            progress.update(process, advance=1)

    return result
