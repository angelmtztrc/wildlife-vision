import pytest

from wv.core.detection import classify_detections, validate_detection_settings
from wv.ml.megadetector import MlDetection


def test_classify_detections_uses_configured_ambiguity_gap():
    detections = [MlDetection("animal", 0.8), MlDetection("human", 0.6)]

    assert classify_detections(detections, 0.7, 0.3).label == "other"
    assert classify_detections(detections, 0.7, 0.2).label == "animal"


@pytest.mark.parametrize(
    ("confidence_threshold", "ambiguity_gap", "batch_size"),
    [(float("nan"), 0.3, 1), (0.8, float("inf"), 1), (0.8, 0.3, 0)],
)
def test_validate_detection_settings_rejects_invalid_values(
    confidence_threshold: float, ambiguity_gap: float, batch_size: int
):
    with pytest.raises(ValueError):
        validate_detection_settings(confidence_threshold, ambiguity_gap, batch_size)
