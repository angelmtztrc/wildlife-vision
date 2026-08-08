from datetime import datetime, timedelta
from pathlib import Path

import imagehash

import wv.core.bursts as bursts
from wv.core.bursts import BurstAnalysis, BurstCandidate, build_burst_reduction_plan


def _candidate(name: str, captured_at: datetime) -> BurstCandidate:
    return BurstCandidate("id-" + name, Path(name), "SITE", captured_at)


def test_create_burst_candidate_parses_ingested_filename(tmp_path: Path):
    file_path = tmp_path / "20240628_101530__GF_STREAM_FEEDER__ABC234.jpg"
    file_path.write_bytes(b"placeholder")

    candidate = bursts.create_burst_candidate("image-1", file_path)

    assert candidate.id == "image-1"
    assert candidate.monitoring_site == "GF_STREAM_FEEDER"
    assert candidate.captured_at == datetime(2024, 6, 28, 10, 15, 30)


def test_plan_keeps_two_images_for_six_member_cluster(monkeypatch):
    start = datetime(2024, 6, 28, 10, 15, 30)
    candidates = [
        _candidate(f"{index}.jpg", start + timedelta(seconds=index))
        for index in range(6)
    ]

    monkeypatch.setattr(
        bursts,
        "_analyze_candidate",
        lambda candidate: BurstAnalysis(
            candidate, imagehash.hex_to_hash("0000000000000000"), 1.0
        ),
    )

    plan = build_burst_reduction_plan(candidates, 60, 0)

    assert plan.bursts == 1
    assert plan.processed == 6
    assert [decision.decision for decision in plan.decisions].count("keep") == 2
    assert [decision.decision for decision in plan.decisions].count("move") == 4


def test_plan_clusters_transitively(monkeypatch):
    start = datetime(2024, 6, 28, 10, 15, 30)
    candidates = [
        _candidate(f"{index}.jpg", start + timedelta(seconds=index))
        for index in range(3)
    ]
    hashes = [
        imagehash.hex_to_hash("0000000000000000"),
        imagehash.hex_to_hash("0000000000000001"),
        imagehash.hex_to_hash("0000000000000003"),
    ]

    monkeypatch.setattr(
        bursts,
        "_analyze_candidate",
        lambda candidate: BurstAnalysis(
            candidate, hashes[int(candidate.path.stem)], 1.0
        ),
    )

    plan = build_burst_reduction_plan(candidates, 60, 1)

    assert [decision.decision for decision in plan.decisions].count("keep") == 1
    assert [decision.decision for decision in plan.decisions].count("move") == 2


def test_plan_uses_path_to_break_equal_quality_ties(monkeypatch):
    start = datetime(2024, 6, 28, 10, 15, 30)
    candidates = [_candidate("b.jpg", start), _candidate("a.jpg", start)]

    monkeypatch.setattr(
        bursts,
        "_analyze_candidate",
        lambda candidate: BurstAnalysis(
            candidate, imagehash.hex_to_hash("0000000000000000"), 1.0
        ),
    )

    plan = build_burst_reduction_plan(candidates, 60, 0)

    decisions = {decision.path.name: decision.decision for decision in plan.decisions}
    assert decisions == {"a.jpg": "keep", "b.jpg": "move"}


def test_plan_reports_analysis_failure_without_selecting_it(monkeypatch):
    candidate = _candidate("broken.jpg", datetime(2024, 6, 28, 10, 15, 30))

    def fail_analysis(candidate):
        if candidate.path.name == "broken.jpg":
            raise OSError("cannot decode")
        return BurstAnalysis(
            candidate, imagehash.hex_to_hash("0000000000000000"), 1.0
        )

    monkeypatch.setattr(bursts, "_analyze_candidate", fail_analysis)

    processed_candidates = 0

    def on_candidate_processed():
        nonlocal processed_candidates
        processed_candidates += 1

    plan = build_burst_reduction_plan(
        [candidate, _candidate("other.jpg", candidate.captured_at + timedelta(seconds=1))],
        60,
        0,
        on_candidate_processed=on_candidate_processed,
    )

    assert len(plan.failures) == 1
    assert processed_candidates == 2
    assert (
        next(
            decision
            for decision in plan.decisions
            if decision.path.name == "broken.jpg"
        ).decision
        == "keep"
    )
