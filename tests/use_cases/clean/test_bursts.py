from pathlib import Path

import pytest

from wv.core.bursts import BurstAnalysis
from wv.use_cases.clean.bursts import CleanBurstsInput, run


def test_run_moves_lower_ranked_images_from_a_burst(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    file_paths = [
        source / "20240628_101530__GF_STREAM_FEEDER__ABC234.jpg",
        source / "20240628_101531__GF_STREAM_FEEDER__ABC235.jpg",
        source / "20240628_101532__GF_STREAM_FEEDER__ABC236.jpg",
    ]
    for path in file_paths:
        path.write_bytes(b"placeholder")

    def fake_plan(candidates, burst_gap_threshold, similarity_threshold):
        from wv.core.bursts import BurstDecision, BurstReductionPlan

        candidates = sorted(candidates, key=lambda candidate: candidate.path.name)

        return BurstReductionPlan(
            decisions=(
                BurstDecision(candidates[0].id, candidates[0].path, "keep"),
                BurstDecision(candidates[1].id, candidates[1].path, "move"),
                BurstDecision(candidates[2].id, candidates[2].path, "move"),
            ),
            failures=(),
            bursts=1,
            processed=3,
        )

    monkeypatch.setattr("wv.use_cases.clean.bursts.build_burst_reduction_plan", fake_plan)

    result = run(CleanBurstsInput(source=source, output=output, similarity_threshold=0))

    destination = output / "ignored" / "bursts"
    assert result.files_discovered == 3
    assert result.files_processed == 3
    assert result.files_bursts == 1
    assert result.files_reduced == 2
    assert result.files_moved == 2
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert file_paths[0].exists()
    assert not file_paths[1].exists()
    assert not file_paths[2].exists()
    assert (destination / file_paths[1].name).exists()
    assert (destination / file_paths[2].name).exists()


def test_run_keeps_singleton_burst_during_dry_run(make_image, tmp_path: Path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    file_path = make_image(
        source / "20240628_101530__GF_STREAM_FEEDER__ABC234.jpg"
    )

    result = run(CleanBurstsInput(source=source, output=output, dry_run=True))

    assert result.files_discovered == 1
    assert result.files_processed == 1
    assert result.files_bursts == 0
    assert result.files_reduced == 0
    assert result.files_moved == 0
    assert result.files_ignored == 1
    assert result.files_failed == 0
    assert file_path.exists()
    assert not (output / "ignored" / "bursts").exists()


@pytest.mark.parametrize(
    ("burst_gap_threshold", "similarity_threshold", "message"),
    [(-1, 5, "burst_gap_threshold"), (60, -1, "similarity_threshold"), (60, 65, "similarity_threshold")],
)
def test_run_rejects_invalid_thresholds(
    tmp_path: Path,
    burst_gap_threshold: int,
    similarity_threshold: int,
    message: str,
):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(ValueError, match=message):
        run(
            CleanBurstsInput(
                source=source,
                output=tmp_path / "output",
                burst_gap_threshold=burst_gap_threshold,
                similarity_threshold=similarity_threshold,
            )
        )
