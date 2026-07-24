from pathlib import Path

import pytest

from wv.cli.commands import ingest
from wv.use_cases.ingest.common import IngestResult
from wv.use_cases.sd import SdError


def test_ingest_sd_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "destination"

    monkeypatch.setattr(
        ingest,
        "run_ingest_sd",
        lambda input_data: IngestResult(
            files_discovered=4,
            files_copied=3,
            files_deleted=1,
            files_ignored=1,
            files_failed=0,
            files_replaced=2,
            destination=destination,
            dry_run=True,
        ),
    )

    result = cli_runner.invoke(ingest.app, ["sd", str(source), "--dry-run"])

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "Starting SD ingest" in result.output
    assert "[DONE]" in result.output
    assert "Finished SD ingest" in result.output
    assert "copied=3" in result.output
    assert "replaced=2" in result.output
    assert "deleted=1" in result.output
    assert "failed=0" in result.output
    assert "(dry run)" in result.output


def test_ingest_sd_reports_missing_config(cli_runner, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    result = cli_runner.invoke(ingest.app, ["sd", str(source)])

    assert result.exit_code == 1
    assert "[ERROR]" in result.output
    assert "SD config file not found" in result.output


def test_ingest_sd_exits_with_code_one_when_use_case_reports_failures(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()

    monkeypatch.setattr(
        ingest,
        "run_ingest_sd",
        lambda input_data: IngestResult(
            files_discovered=1,
            files_failed=1,
            destination=tmp_path / "destination",
        ),
    )

    result = cli_runner.invoke(ingest.app, ["sd", str(source)])

    assert result.exit_code == 1
    assert "[DONE]" in result.output
    assert "failed=1" in result.output


def test_ingest_folder_forwards_option_identity(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    captured_input = None

    def fake_run(input_data):
        nonlocal captured_input
        captured_input = input_data
        return IngestResult(destination=tmp_path / "destination")

    monkeypatch.setattr(ingest, "run_ingest_folder", fake_run)

    result = cli_runner.invoke(
        ingest.app,
        [
            "folder",
            str(source),
            "--device",
            "HNT001",
            "--monitoring-site",
            "SITE001",
            "--mode",
            "copy",
        ],
    )

    assert result.exit_code == 0
    assert captured_input.device_id == "HNT001"
    assert captured_input.monitoring_site_id == "SITE001"
    assert captured_input.mode == "copy"
    assert "Finished folder ingest" in result.output


def test_ingest_folder_requires_identity_options(cli_runner, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    result = cli_runner.invoke(ingest.app, ["folder", str(source)])

    assert result.exit_code != 0
    assert "Missing option" in result.output
