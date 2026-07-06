from pathlib import Path

import pytest

from wv.cli.commands import detect
from wv.use_cases.detect.content import DetectContentResult


def test_detect_content_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    monkeypatch.setattr(
        detect,
        "run_detect_content",
        lambda input_data: DetectContentResult(
            files_discovered=6,
            files_evaluated=5,
            files_moved=5,
            files_ignored=1,
            files_failed=0,
            files_replaced=1,
            files_animal=1,
            files_human=1,
            files_vehicle=1,
            files_empty=1,
            files_other=1,
            destination=output / "detection",
            dry_run=True,
        ),
    )

    result = cli_runner.invoke(
        detect.app,
        [str(source), "--output", str(output), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "Starting content detection" in result.output
    assert "[DONE]" in result.output
    assert "Finished content detection" in result.output
    assert "evaluated=5" in result.output
    assert "animal=1" in result.output
    assert "human=1" in result.output
    assert "vehicle=1" in result.output
    assert "empty=1" in result.output
    assert "other=1" in result.output
    assert "moved=5" in result.output
    assert "replaced=1" in result.output
    assert "failed=0" in result.output
    assert "(dry run)" in result.output


def test_detect_content_exits_with_code_one_when_use_case_reports_failures(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    monkeypatch.setattr(
        detect,
        "run_detect_content",
        lambda input_data: DetectContentResult(
            files_failed=1,
            destination=output / "detection",
        ),
    )

    result = cli_runner.invoke(
        detect.app,
        [str(source), "--output", str(output)],
    )

    assert result.exit_code == 1
    assert "[DONE]" in result.output
    assert "failed=1" in result.output
