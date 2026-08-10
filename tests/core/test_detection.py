import pytest

from wv.core.detection import (
    DEFAULT_BATCH_SIZE,
    SpeciesNetClassification,
    classify_detections,
    validate_detection_settings,
)
from wv.ml.megadetector import MlDetection


def test_classify_detections_uses_human_first_precedence():
    detections = [MlDetection("animal", 0.9), MlDetection("human", 0.2)]

    assert classify_detections(detections, {}).label == "human"


def test_classify_detections_uses_speciesnet_domestic_result():
    detections = [MlDetection("animal", 0.9)]

    decision = classify_detections(
        detections, {0: SpeciesNetClassification("domestic", 0.95)}
    )

    assert decision.label == "domestic"
    assert decision.confidence == 0.95
    assert decision.source == "ensemble"


def test_classify_detections_uses_speciesnet_blank_when_it_has_higher_confidence():
    decision = classify_detections(
        [MlDetection("animal", 0.371)],
        {0: SpeciesNetClassification("blank", 0.93645)},
    )

    assert decision.label == "empty"
    assert decision.confidence == 0.93645
    assert decision.source == "ensemble"


def test_classify_detections_allows_speciesnet_to_promote_animal_detection():
    decision = classify_detections(
        [MlDetection("animal", 0.15)],
        {0: SpeciesNetClassification("animal", 0.85)},
    )

    assert decision.label == "animal"
    assert decision.confidence == 0.85
    assert decision.source == "ensemble"


def test_classify_detections_uses_megadetector_for_equal_confidence():
    decision = classify_detections(
        [MlDetection("animal", 0.4)],
        {0: SpeciesNetClassification("blank", 0.4)},
    )

    assert decision.label == "animal"
    assert decision.confidence == 0.4
    assert decision.source == "ensemble"


def test_classify_detections_keeps_animal_when_another_crop_is_blank():
    decision = classify_detections(
        [MlDetection("animal", 0.371), MlDetection("animal", 0.6)],
        {
            0: SpeciesNetClassification("blank", 0.93645),
            1: SpeciesNetClassification("animal", 0.8),
        },
    )

    assert decision.label == "animal"
    assert decision.confidence == 0.8


def test_classify_detections_routes_low_confidence_paired_result_to_other():
    decision = classify_detections(
        [MlDetection("animal", 0.15)],
        {0: SpeciesNetClassification("blank", 0.18)},
    )

    assert decision.label == "other"


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
