from pathlib import Path

import pytest

from wv.cli.commands import ingest
from wv.use_cases.ingest.sd import IngestSdResult


def test_ingest_sd_rejects_unknown_device(cli_runner, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    result = cli_runner.invoke(
        ingest.app,
        [
            "sd",
            str(source),
            "--device",
            "UNKNOWN",
            "--monitoring-site",
            "GF_STREAM_FEEDER",
        ],
    )

    assert result.exit_code != 0
    assert "Unknown device 'UNKNOWN'." in result.output


def test_ingest_sd_rejects_unknown_monitoring_site(cli_runner, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    result = cli_runner.invoke(
        ingest.app,
        [
            "sd",
            str(source),
            "--device",
            "HNT001",
            "--monitoring-site",
            "UNKNOWN_SITE",
        ],
    )

    assert result.exit_code != 0
    assert "UNKNOWN_SITE" in result.output
    assert "monitoring-site" in result.output


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
        lambda input_data: IngestSdResult(
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

    result = cli_runner.invoke(
        ingest.app,
        [
            "sd",
            str(source),
            "--device",
            "HNT001",
            "--monitoring-site",
            "GF_STREAM_FEEDER",
            "--dry-run",
        ],
    )

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
        lambda input_data: IngestSdResult(
            files_discovered=1,
            files_failed=1,
            destination=tmp_path / "destination",
        ),
    )

    result = cli_runner.invoke(
        ingest.app,
        [
            "sd",
            str(source),
            "--device",
            "HNT001",
            "--monitoring-site",
            "GF_STREAM_FEEDER",
        ],
    )

    assert result.exit_code == 1
    assert "[DONE]" in result.output
    assert "failed=1" in result.output
