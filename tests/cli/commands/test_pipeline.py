from pathlib import Path

import pytest

from wv.cli.commands import pipeline
from wv.use_cases.clean.bursts import CleanBurstsResult
from wv.use_cases.clean.corrupted import CleanCorruptedResult
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrResult
from wv.use_cases.detect.content import DetectContentResult
from wv.use_cases.pipeline.preprocess import PipelinePreprocessResult


def test_pipeline_preprocess_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session_path = tmp_path / "20260707_101530__Camera_01"
    initial_path = session_path / "initial"
    initial_path.mkdir(parents=True)

    monkeypatch.setattr(
        pipeline,
        "run_pipeline_preprocess",
        lambda input_data: PipelinePreprocessResult(
            session_path=session_path,
            initial_path=initial_path,
            corrupted_result=CleanCorruptedResult(files_corrupted=1, destination=session_path / "ignored" / "corrupted"),
            overexposed_result=CleanOverexposedIrResult(files_overexposed=2, destination=session_path / "ignored" / "overexposed"),
            bursts_result=CleanBurstsResult(files_reduced=3, destination=session_path / "ignored" / "bursts"),
            detect_result=DetectContentResult(files_evaluated=4, files_moved=4, destination=session_path / "detection"),
            files_failed=0,
            files_remaining_in_initial=1,
            dry_run=True,
        ),
    )

    result = cli_runner.invoke(
        pipeline.app,
        [str(session_path), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "Starting preprocess pipeline" in result.output
    assert "[DONE]" in result.output
    assert "Finished preprocess pipeline" in result.output
    assert "corrupted=1" in result.output
    assert "overexposed=2" in result.output
    assert "reduced=3" in result.output
    assert "evaluated=4" in result.output
    assert "moved=4" in result.output
    assert "failed=0" in result.output
    assert "remaining_in_initial=1" in result.output
    assert "(dry run)" in result.output


def test_pipeline_preprocess_exits_with_code_one_when_use_case_reports_failures(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    session_path = tmp_path / "20260707_101530__Camera_01"
    initial_path = session_path / "initial"
    initial_path.mkdir(parents=True)

    monkeypatch.setattr(
        pipeline,
        "run_pipeline_preprocess",
        lambda input_data: PipelinePreprocessResult(
            session_path=session_path,
            initial_path=initial_path,
            corrupted_result=CleanCorruptedResult(destination=session_path / "ignored" / "corrupted"),
            overexposed_result=CleanOverexposedIrResult(destination=session_path / "ignored" / "overexposed"),
            bursts_result=CleanBurstsResult(destination=session_path / "ignored" / "bursts"),
            detect_result=DetectContentResult(destination=session_path / "detection"),
            files_failed=1,
            files_remaining_in_initial=2,
            dry_run=False,
        ),
    )

    result = cli_runner.invoke(
        pipeline.app,
        [str(session_path)],
    )

    assert result.exit_code == 1
    assert "[DONE]" in result.output
    assert "failed=1" in result.output


def test_pipeline_preprocess_rejects_invalid_session_path(
    cli_runner,
    tmp_path: Path,
):
    session_path = tmp_path / "invalid-session"
    session_path.mkdir()

    result = cli_runner.invoke(
        pipeline.app,
        [str(session_path)],
    )

    assert result.exit_code != 0
    assert "YYYYMMDD_HHMMSS__CAMERA" in result.output
