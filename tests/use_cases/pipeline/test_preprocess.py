from pathlib import Path

import pytest

import wv.use_cases.pipeline.preprocess as preprocess
from wv.use_cases.clean.bursts import CleanBurstsResult
from wv.use_cases.clean.corrupted import CleanCorruptedResult
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrResult
from wv.use_cases.detect.content import DetectContentResult
from wv.use_cases.pipeline.preprocess import PipelinePreprocessInput, run


def test_run_delegates_steps_in_order_and_aggregates_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session_path = tmp_path / "20260707_101530__Camera_01"
    init_path = session_path / "init"
    init_path.mkdir(parents=True)
    leftover = init_path / "leftover.txt"
    leftover.write_text("unsupported")

    calls: list[tuple[str, object]] = []

    def fake_clean_corrupted(input_data):
        calls.append(("corrupted", input_data))
        return CleanCorruptedResult(files_corrupted=1, files_moved=1, destination=session_path / "ignored" / "corrupted")

    def fake_clean_overexposed(input_data):
        calls.append(("overexposed", input_data))
        return CleanOverexposedIrResult(files_overexposed=2, files_moved=2, destination=session_path / "ignored" / "overexposed")

    def fake_clean_bursts(input_data):
        calls.append(("bursts", input_data))
        return CleanBurstsResult(files_reduced=3, files_moved=3, destination=session_path / "ignored" / "bursts")

    def fake_detect_content(input_data):
        calls.append(("detect", input_data))
        return DetectContentResult(files_evaluated=4, files_moved=4, destination=session_path / "detection")

    monkeypatch.setattr(preprocess, "run_clean_corrupted", fake_clean_corrupted)
    monkeypatch.setattr(preprocess, "run_clean_overexposed_ir", fake_clean_overexposed)
    monkeypatch.setattr(preprocess, "run_clean_bursts", fake_clean_bursts)
    monkeypatch.setattr(preprocess, "run_detect_content", fake_detect_content)

    result = run(
        PipelinePreprocessInput(
            session_path=session_path,
            mean_threshold=210.0,
            std_threshold=20.0,
            high_level=225,
            ptc_high_threshold=0.75,
            burst_gap_threshold=30,
            similarity_threshold=7,
            model="custom-model",
            confidence_threshold=0.9,
            batch_size=8,
            dry_run=True,
        )
    )

    assert [name for name, _ in calls] == ["corrupted", "overexposed", "bursts", "detect"]

    corrupted_input = calls[0][1]
    overexposed_input = calls[1][1]
    bursts_input = calls[2][1]
    detect_input = calls[3][1]

    assert corrupted_input.source == init_path
    assert corrupted_input.output == session_path
    assert corrupted_input.dry_run is True

    assert overexposed_input.source == init_path
    assert overexposed_input.output == session_path
    assert overexposed_input.mean_threshold == 210.0
    assert overexposed_input.std_threshold == 20.0
    assert overexposed_input.high_level == 225
    assert overexposed_input.ptc_high_threshold == 0.75
    assert overexposed_input.dry_run is True

    assert bursts_input.source == init_path
    assert bursts_input.output == session_path
    assert bursts_input.burst_gap_threshold == 30
    assert bursts_input.similarity_threshold == 7
    assert bursts_input.dry_run is True

    assert detect_input.source == init_path
    assert detect_input.output == session_path
    assert detect_input.model == "custom-model"
    assert detect_input.confidence_threshold == 0.9
    assert detect_input.batch_size == 8
    assert detect_input.dry_run is True

    assert result.session_path == session_path
    assert result.init_path == init_path
    assert result.files_failed == 0
    assert result.files_remaining_in_init == 1
    assert result.dry_run is True


def test_run_rejects_invalid_session_folder_name(tmp_path: Path):
    session_path = tmp_path / "not-a-session"
    (session_path / "init").mkdir(parents=True)

    with pytest.raises(ValueError, match="YYYYMMDD_HHMMSS__CAMERA"):
        run(PipelinePreprocessInput(session_path=session_path))


def test_run_rejects_missing_init_directory(tmp_path: Path):
    session_path = tmp_path / "20260707_101530__camera01"
    session_path.mkdir()

    with pytest.raises(FileNotFoundError, match="expected init directory"):
        run(PipelinePreprocessInput(session_path=session_path))


def test_run_accepts_mixed_case_camera_segment_and_aggregates_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session_path = tmp_path / "20260707_101530__CameraOne"
    init_path = session_path / "init"
    init_path.mkdir(parents=True)

    monkeypatch.setattr(
        preprocess,
        "run_clean_corrupted",
        lambda input_data: CleanCorruptedResult(
            files_failed=1, destination=session_path / "ignored" / "corrupted"
        ),
    )
    monkeypatch.setattr(
        preprocess,
        "run_clean_overexposed_ir",
        lambda input_data: CleanOverexposedIrResult(
            files_failed=2, destination=session_path / "ignored" / "overexposed"
        ),
    )
    monkeypatch.setattr(
        preprocess,
        "run_clean_bursts",
        lambda input_data: CleanBurstsResult(
            files_failed=3, destination=session_path / "ignored" / "bursts"
        ),
    )
    monkeypatch.setattr(
        preprocess,
        "run_detect_content",
        lambda input_data: DetectContentResult(
            files_failed=4, destination=session_path / "detection"
        ),
    )

    result = run(PipelinePreprocessInput(session_path=session_path))

    assert result.init_path == init_path
    assert result.files_failed == 10
    assert result.files_remaining_in_init == 0
