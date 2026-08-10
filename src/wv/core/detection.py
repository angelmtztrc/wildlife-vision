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


@dataclass(frozen=True)
class SpeciesNetClassification:
    """A semantic SpeciesNet classification for one MegaDetector animal crop."""

    label: str
    confidence: float


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
    detections: list[MlDetection],
    speciesnet_classifications: dict[int, SpeciesNetClassification],
) -> DetectionDecision:
    """Classify MegaDetector detections into a session route.

    Args:
        detections: Normalized MegaDetector detections for one image.
        speciesnet_classifications: SpeciesNet results for MegaDetector animal
            detection indexes that met the crop-classification gate.

    Returns:
        An ``animal``, ``human``, ``vehicle``, ``domestic``, ``empty``, or
        ``other`` decision.

    Raises:
        ValueError: If detector confidence values are non-finite or outside
            the inclusive ``[0, 1]`` range.
    """
    accepted: dict[str, list[DetectionDecision]] = {
        "human": [],
        "vehicle": [],
        "domestic": [],
        "animal": [],
        "other": [],
    }
    blank_confidences: list[float] = []
    unresolved = False

    for index, detection in enumerate(detections):
        if not isfinite(detection.confidence) or not 0.0 <= detection.confidence <= 1.0:
            raise ValueError("Detector confidence must be between 0.0 and 1.0.")

        if detection.label in {"human", "vehicle"}:
            if detection.confidence >= TRUSTED_CONTENT_THRESHOLD:
                accepted[detection.label].append(
                    DetectionDecision(detection.label, detection.confidence, "megadetector")
                )
            elif detection.confidence >= CLASSIFICATION_GATE:
                unresolved = True
            continue

        if detection.label != "animal":
            if detection.confidence >= CLASSIFICATION_GATE:
                accepted["other"].append(
                    DetectionDecision("other", detection.confidence, "megadetector")
                )
            continue

        if detection.confidence < CLASSIFICATION_GATE:
            continue

        speciesnet = speciesnet_classifications.get(index)
        if speciesnet is None:
            winner = DetectionDecision("animal", detection.confidence, "megadetector")
        else:
            _validate_speciesnet_classification(speciesnet)
            winner = DetectionDecision("animal", detection.confidence, "ensemble")
            if speciesnet.confidence > detection.confidence:
                winner = DetectionDecision(speciesnet.label, speciesnet.confidence, "ensemble")

        if winner.confidence < TRUSTED_CONTENT_THRESHOLD:
            unresolved = True
        elif winner.label == "blank":
            blank_confidences.append(winner.confidence)
        else:
            accepted[winner.label].append(winner)

    for label in ("human", "vehicle", "domestic", "animal", "other"):
        if accepted[label]:
            winner = max(accepted[label], key=lambda item: item.confidence)
            return winner
    if blank_confidences:
        return DetectionDecision("empty", max(blank_confidences), "ensemble")
    if not unresolved:
        return DetectionDecision("empty", 0.0, "megadetector")
    return DetectionDecision("other", 0.0, "ensemble")


def _validate_speciesnet_classification(classification: SpeciesNetClassification) -> None:
    if classification.label not in {"animal", "blank", "domestic", "human", "other", "vehicle"}:
        raise ValueError("SpeciesNet classification label is unsupported.")
    if not isfinite(classification.confidence) or not 0.0 <= classification.confidence <= 1.0:
        raise ValueError("SpeciesNet classification confidence must be between 0.0 and 1.0.")
