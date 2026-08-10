"""Content-detection settings and routing helpers."""

from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from wv.ml.megadetector import MlDetection

DEFAULT_BATCH_SIZE = 4
MINIMUM_DETECTION_THRESHOLD = 0.005
CLASSIFICATION_GATE = 0.1
TRUSTED_CONTENT_THRESHOLD = 0.2
TAXONOMIC_ROLLUP_THRESHOLD = 0.65


@dataclass(frozen=True)
class DetectionDecision:
    """The classified label and confidence for one image."""

    label: str
    confidence: float
    source: str


def validate_detection_settings(batch_size: int, domestic_taxon_ids: list[str]) -> None:
    """Validate content-detection inference settings.

    Args:
        batch_size: Number of images evaluated together by the detector.
        domestic_taxon_ids: SpeciesNet taxonomy identifiers treated as domestic.

    Raises:
        ValueError: If a setting is non-finite or outside its supported range.
    """
    if isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if len(domestic_taxon_ids) != len(set(domestic_taxon_ids)):
        raise ValueError("domestic_taxon_ids must not contain duplicates.")
    if any(not isinstance(taxon_id, str) or not taxon_id.strip() for taxon_id in domestic_taxon_ids):
        raise ValueError("domestic_taxon_ids must contain non-empty strings.")
    try:
        for taxon_id in domestic_taxon_ids:
            UUID(taxon_id)
    except ValueError as exc:
        raise ValueError("domestic_taxon_ids must contain UUID strings.") from exc


def classify_detections(
    detections: list[MlDetection], domestic_detection_indexes: set[int]
) -> DetectionDecision:
    """Classify MegaDetector detections into a session route.

    Args:
        detections: Normalized MegaDetector detections for one image.
        domestic_detection_indexes: Indexes of animal detections resolved to a
            configured domestic SpeciesNet taxon.

    Returns:
        An ``animal``, ``human``, ``vehicle``, ``domestic``, ``empty``, or
        ``other`` decision.

    Raises:
        ValueError: If detector confidence values are non-finite or outside
            the inclusive ``[0, 1]`` range.
    """
    trusted: list[tuple[int, MlDetection]] = []
    meaningful: list[tuple[int, MlDetection]] = []
    for index, detection in enumerate(detections):
        if not isfinite(detection.confidence) or not 0.0 <= detection.confidence <= 1.0:
            raise ValueError("Detector confidence must be between 0.0 and 1.0.")
        if detection.confidence >= CLASSIFICATION_GATE:
            meaningful.append((index, detection))
        if detection.confidence >= TRUSTED_CONTENT_THRESHOLD:
            trusted.append((index, detection))

    for label in ("human", "vehicle"):
        matches = [detection for _, detection in trusted if detection.label == label]
        if matches:
            return DetectionDecision(label, max(item.confidence for item in matches), "megadetector")

    domestic = [
        detection
        for index, detection in trusted
        if detection.label == "animal" and index in domestic_detection_indexes
    ]
    if domestic:
        return DetectionDecision("domestic", max(item.confidence for item in domestic), "speciesnet")

    animals = [detection for _, detection in trusted if detection.label == "animal"]
    if animals:
        return DetectionDecision("animal", max(item.confidence for item in animals), "megadetector")
    if not meaningful:
        return DetectionDecision("empty", 0.0, "megadetector")
    return DetectionDecision(
        "other",
        max(item.confidence for _, item in meaningful),
        "megadetector",
    )
