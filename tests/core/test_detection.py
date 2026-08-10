import pytest

from wv.core.detection import (
    DEFAULT_BATCH_SIZE,
    classify_detections,
    validate_detection_settings,
)
from wv.ml.megadetector import MlDetection


def test_classify_detections_uses_human_first_precedence():
    detections = [MlDetection("animal", 0.9), MlDetection("human", 0.2)]

    assert classify_detections(detections, set()).label == "human"


def test_classify_detections_uses_speciesnet_domestic_result():
    detections = [MlDetection("animal", 0.9)]

    assert classify_detections(detections, {0}).label == "domestic"


def test_default_batch_size_is_conservative():
    assert DEFAULT_BATCH_SIZE == 4


@pytest.mark.parametrize(
    ("batch_size", "domestic_taxon_ids"),
    [(0, []), (1, ["00000000-0000-0000-0000-000000000000"] * 2), (1, [""])],
)
def test_validate_detection_settings_rejects_invalid_values(
    batch_size: int, domestic_taxon_ids: list[str]
):
    with pytest.raises(ValueError):
        validate_detection_settings(batch_size, domestic_taxon_ids)
