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
    assert f"Source: {source}" in result.output
    assert f"Destination: {destination}" in result.output
    assert "Copied: 3" in result.output
    assert "Replaced: 2" in result.output
    assert "Deleted: 1" in result.output
    assert "Dry run: yes" in result.output
    assert "[OK]" in result.output


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
    assert "Failed: 1" in result.output
    assert "[ERROR]" in result.output
