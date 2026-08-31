from pathlib import Path

import pytest

from wv.cli.commands import export
from wv.use_cases.session.export_favorites import ExportFavoritesResult


def test_export_favorites_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "custom-export"

    monkeypatch.setattr(
        export,
        "run_export_favorites",
        lambda input_data: ExportFavoritesResult(
            files_discovered=6,
            files_export_candidates=2,
            files_exported=2,
            files_skipped=4,
            files_failed=0,
            files_replaced=1,
            destination=output,
            dry_run=True,
        ),
    )

    result = cli_runner.invoke(
        export.app,
        ["SESSION001", "--output", str(output), "--dry-run"],
    )

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "Starting favorite export" in result.output
    assert "[DONE]" in result.output
    assert "Finished favorite export" in result.output
    assert "candidates=2" in result.output
    assert "exported=2" in result.output
    assert "replaced=1" in result.output
    assert "skipped=4" in result.output
    assert "failed=0" in result.output
    assert "(dry run)" in result.output


def test_export_favorites_exits_with_code_one_when_use_case_reports_failures(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        export,
        "run_export_favorites",
        lambda input_data: ExportFavoritesResult(
            files_failed=1,
            destination=tmp_path / "custom-export",
        ),
    )

    result = cli_runner.invoke(export.app, ["SESSION001"])

    assert result.exit_code == 1
    assert "[DONE]" in result.output
    assert "failed=1" in result.output
