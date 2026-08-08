"""Content-detection classification and metadata helpers."""

from dataclasses import dataclass
from math import isfinite

from wv.core.metadata import upsert_image_description_properties
from wv.ml.megadetector import MlDetection

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_AMBIGUITY_GAP = 0.3
DEFAULT_BATCH_SIZE = 4


@dataclass(frozen=True)
class DetectionDecision:
    """The classified label and confidence for one image."""

    label: str
    confidence: float


def validate_detection_settings(
    confidence_threshold: float, ambiguity_gap: float, batch_size: int
) -> None:
    """Validate detection classification and inference settings.

    Args:
        confidence_threshold: Minimum confidence required for a primary label.
        ambiguity_gap: Minimum lead over a second label required to disambiguate.
        batch_size: Number of images evaluated together by the detector.

    Raises:
        ValueError: If a setting is non-finite or outside its supported range.
    """
    if not isfinite(confidence_threshold) or not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.0 and 1.0.")
    if not isfinite(ambiguity_gap) or not 0.0 <= ambiguity_gap <= 1.0:
        raise ValueError("ambiguity_gap must be between 0.0 and 1.0.")
    if isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError("batch_size must be at least 1.")


def classify_detections(
    detections: list[MlDetection], confidence_threshold: float, ambiguity_gap: float
) -> DetectionDecision:
    """Classify normalized MegaDetector detections into a session route.

    Args:
        detections: Normalized label/confidence detections for one image.
        confidence_threshold: Minimum confidence for animal, human, or vehicle.
        ambiguity_gap: Required confidence lead over the second-best label.

    Returns:
        An ``animal``, ``human``, ``vehicle``, ``empty``, or ``other`` decision.

    Raises:
        ValueError: If detector confidence values are non-finite or outside
            the inclusive ``[0, 1]`` range.
    """
    if not detections:
        return DetectionDecision(label="empty", confidence=0.0)

    confidence_by_label: dict[str, float] = {}
    for detection in detections:
        if not isfinite(detection.confidence) or not 0.0 <= detection.confidence <= 1.0:
            raise ValueError("Detector confidence must be between 0.0 and 1.0.")
        confidence_by_label[detection.label] = max(
            confidence_by_label.get(detection.label, 0.0), detection.confidence
        )

    ranked_labels = sorted(
        confidence_by_label.items(), key=lambda item: (-item[1], item[0])
    )
    best_label, best_confidence = ranked_labels[0]
    if best_confidence < confidence_threshold:
        return DetectionDecision(label="other", confidence=best_confidence)
    if (
        len(ranked_labels) > 1
        and best_confidence - ranked_labels[1][1] < ambiguity_gap
    ):
        return DetectionDecision(label="other", confidence=best_confidence)
    return DetectionDecision(label=best_label, confidence=best_confidence)


def format_detection_confidence(confidence: float) -> str:
    """Format a detection confidence for durable EXIF metadata."""
    return f"{confidence:.6f}".rstrip("0").rstrip(".") or "0"


def build_detection_description(
    existing_description: str | None, decision: DetectionDecision
) -> str:
    """Return canonical EXIF description text containing a detection decision."""
    return upsert_image_description_properties(
        existing_description,
        {
            "Detection": decision.label,
            "Detection_Confidence": format_detection_confidence(decision.confidence),
        },
    )
