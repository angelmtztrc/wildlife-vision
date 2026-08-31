from pathlib import Path

import pytest

from wv.cli.commands import ingest
from wv.use_cases.ingest.ingest import (
    ExplicitIngestIdentity,
    IngestResult,
    SdCardIngestIdentity,
)
from wv.use_cases.monitoring_site.list import ListMonitoringSitesResult
from wv.workspace.common import WorkspaceError


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
        "run_ingest",
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
        "run_ingest",
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

    monkeypatch.setattr(ingest, "run_ingest", fake_run)

    result = cli_runner.invoke(
        ingest.app,
        [
            "folder",
            str(source),
            "--monitoring-site",
            "SITE001",
            "--mode",
            "copy",
            "--recursive",
        ],
    )

    assert result.exit_code == 0
    assert isinstance(captured_input.identity, ExplicitIngestIdentity)
    assert captured_input.identity.monitoring_site_id == "SITE001"
    assert captured_input.mode == "copy"
    assert captured_input.recursive is True
    assert "Finished folder ingest" in result.output


def test_ingest_folder_requires_identity_options(cli_runner, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    result = cli_runner.invoke(ingest.app, ["folder", str(source)])

    assert result.exit_code != 0
    assert "Missing option" in result.output


def test_ingest_sd_forwards_options_to_use_case(
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

    monkeypatch.setattr(ingest, "run_ingest", fake_run)

    result = cli_runner.invoke(ingest.app, ["sd", str(source), "--mode", "copy"])

    assert result.exit_code == 0
    assert captured_input.mode == "copy"
    assert captured_input.recursive is False
    assert isinstance(captured_input.identity, SdCardIngestIdentity)


def test_ingest_sd_forwards_recursive_option(
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

    monkeypatch.setattr(ingest, "run_ingest", fake_run)

    result = cli_runner.invoke(ingest.app, ["sd", str(source), "--recursive"])

    assert result.exit_code == 0
    assert captured_input.recursive is True


def test_complete_monitoring_site_matches_registered_ids(
    monkeypatch: pytest.MonkeyPatch,
):
    class MonitoringSite:
        def __init__(self, site_id: str):
            self.id = site_id

    monkeypatch.setattr(
        ingest,
        "run_list_monitoring_sites",
        lambda input_data: ListMonitoringSitesResult(
            items=[MonitoringSite("SITE001"), MonitoringSite("PARK001")]
        ),
    )

    assert ingest._complete_monitoring_site("SITE") == ["SITE001"]


def test_completion_returns_no_suggestions_without_workspace(
    monkeypatch: pytest.MonkeyPatch,
):
    def raise_workspace_error(input_data):
        raise WorkspaceError("No workspace configured")

    monkeypatch.setattr(ingest, "run_list_monitoring_sites", raise_workspace_error)

    assert ingest._complete_monitoring_site("") == []
