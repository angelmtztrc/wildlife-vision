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
    assert f"Source: {source}" in result.output
    assert f"Destination: {output / 'detection'}" in result.output
    assert "Evaluated: 5" in result.output
    assert "Animal: 1" in result.output
    assert "Human: 1" in result.output
    assert "Vehicle: 1" in result.output
    assert "Empty: 1" in result.output
    assert "Other: 1" in result.output
    assert "Moved: 5" in result.output
    assert "Replaced: 1" in result.output
    assert "Dry run: yes" in result.output


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
    assert "Failed: 1" in result.output
