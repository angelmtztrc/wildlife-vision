from wv.domain.session import IngestSession, SessionImageStateCount
from wv.cli.main import app
from wv.use_cases.session.list import ListSessionsResult
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedResult
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrResult,
)
from wv.use_cases.session.clean_bursts import SessionCleanBurstsResult
from wv.use_cases.session.detect_content import SessionDetectContentResult
from wv.use_cases.session.status import (
    SessionStageStatus,
    SessionStatusResult,
)
from wv.use_cases.session._shared import SessionError, SessionProcessError


def test_session_list_forwards_filters_and_prints_rows(cli_runner, monkeypatch):
    received_input = None

    def fake_run(input_data):
        nonlocal received_input
        received_input = input_data
        return ListSessionsResult(
            items=[
                IngestSession(
                    id="20260801_120000__SITE001",
                    monitoring_site_id="SITE001",
                    source_path="/Volumes/SD",
                    mode="copy",
                    recursive=False,
                    started_at="2026-08-01T12:00:00+00:00",
                    ingest_status="completed",
                )
            ]
        )

    monkeypatch.setattr("wv.cli.commands.session.run_list_sessions", fake_run)

    result = cli_runner.invoke(
        app,
        [
            "session",
            "list",
            "--monitoring-site",
            "SITE001",
            "--ingest-status",
            "completed",
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert received_input.monitoring_site_id == "SITE001"
    assert received_input.ingest_status == "completed"
    assert received_input.limit == 5
    assert result.output.strip() == (
        "20260801_120000__SITE001\t2026-08-01T12:00:00+00:00\t"
        "SITE001\tcompleted"
    )


def test_session_list_reports_session_errors(cli_runner, monkeypatch):
    def fail_run(input_data):
        raise SessionError("Unknown ingest status: invalid")

    monkeypatch.setattr("wv.cli.commands.session.run_list_sessions", fail_run)

    result = cli_runner.invoke(
        app, ["session", "list", "--ingest-status", "invalid"]
    )

    assert result.exit_code == 1
    assert "Unknown ingest status" in result.output


def test_session_status_prints_operational_details(cli_runner, monkeypatch):
    session = IngestSession(
        id="20260801_120000__SITE001",
        monitoring_site_id="SITE001",
        source_path="/Volumes/SD",
        mode="copy",
        recursive=False,
        started_at="2026-08-01T12:00:00+00:00",
        ingest_status="completed",
        files_discovered=2,
        files_copied=2,
    )
    monkeypatch.setattr(
        "wv.cli.commands.session.run_session_status",
        lambda input_data: SessionStatusResult(
            session=session,
            overall_status="processing",
            next_process="clean_overexposed_ir",
            next_action="run",
            stages=[
                SessionStageStatus(
                    name="clean_corrupted",
                    status="completed",
                    attempt_count=1,
                    files_processed=2,
                ),
                SessionStageStatus(name="clean_overexposed_ir"),
            ],
            inventory=[SessionImageStateCount(state="init", count=2)],
        ),
    )

    result = cli_runner.invoke(
        app, ["session", "status", "20260801_120000__HNT001"]
    )

    assert result.exit_code == 0
    assert "overall_status: processing" in result.output
    assert "next_action: run clean_overexposed_ir" in result.output
    assert "next_parameters:" in result.output
    assert "inventory.init: 2" in result.output
    assert "process.clean_corrupted.status: completed" in result.output
    assert "process.clean_corrupted.parameters:" in result.output
    assert "process.clean_overexposed_ir.status: not_started" in result.output


def test_session_status_reports_unknown_session(cli_runner, monkeypatch):
    def fail_run(input_data):
        raise SessionError(f"Session not found: {input_data.session_id}")

    monkeypatch.setattr("wv.cli.commands.session.run_session_status", fail_run)

    result = cli_runner.invoke(app, ["session", "status", "MISSING"])

    assert result.exit_code == 1
    assert "Session not found: MISSING" in result.output


def test_session_clean_corrupted_prints_summary(cli_runner, monkeypatch):
    def fake_run(input_data):
        return SessionCleanCorruptedResult(
            session_id=input_data.session_id,
            process=None,
            files_corrupted=1,
            files_moved=1,
        )

    monkeypatch.setattr("wv.cli.commands.session.run_clean_corrupted", fake_run)

    result = cli_runner.invoke(app, ["session", "clean", "corrupted", "session-1"])

    assert result.exit_code == 0
    assert "Finished managed corrupted cleanup for session-1" in result.output
    assert "corrupted=1" in result.output


def test_session_clean_overexposed_ir_forwards_options(cli_runner, monkeypatch):
    received_input = None

    def fake_run(input_data):
        nonlocal received_input
        received_input = input_data
        return SessionCleanOverexposedIrResult(
            session_id=input_data.session_id,
            process=None,
            files_processed=2,
            files_overexposed=1,
            files_moved=1,
        )

    monkeypatch.setattr("wv.cli.commands.session.run_clean_overexposed_ir", fake_run)

    result = cli_runner.invoke(
        app,
        [
            "session",
            "clean",
            "overexposed-ir",
            "session-1",
            "--mean-threshold",
            "210",
            "--std-threshold",
            "20",
            "--high-level",
            "225",
            "--pct-high-threshold",
            "0.75",
            "--dry-run",
            "--recover",
        ],
    )

    assert result.exit_code == 0
    assert received_input.mean_threshold == 210.0
    assert received_input.std_threshold == 20.0
    assert received_input.high_level == 225
    assert received_input.pct_high_threshold == 0.75
    assert received_input.dry_run is True
    assert received_input.recover is True
    assert "Finished managed overexposed cleanup for session-1" in result.output


def test_session_clean_overexposed_ir_exits_with_file_failures(
    cli_runner, monkeypatch
):
    monkeypatch.setattr(
        "wv.cli.commands.session.run_clean_overexposed_ir",
        lambda input_data: SessionCleanOverexposedIrResult(
            session_id=input_data.session_id,
            process=None,
            files_failed=1,
        ),
    )

    result = cli_runner.invoke(
        app, ["session", "clean", "overexposed-ir", "session-1"]
    )

    assert result.exit_code == 1


def test_session_clean_bursts_forwards_options(cli_runner, monkeypatch):
    received_input = None

    def fake_run(input_data):
        nonlocal received_input
        received_input = input_data
        return SessionCleanBurstsResult(
            session_id=input_data.session_id,
            process=None,
            files_bursts=1,
            files_reduced=2,
            files_moved=2,
        )

    monkeypatch.setattr("wv.cli.commands.session.run_clean_bursts", fake_run)

    result = cli_runner.invoke(
        app,
        [
            "session",
            "clean",
            "bursts",
            "session-1",
            "--burst-gap-threshold",
            "30",
            "--similarity-threshold",
            "7",
            "--dry-run",
            "--recover",
        ],
    )

    assert result.exit_code == 0
    assert received_input.burst_gap_threshold == 30
    assert received_input.similarity_threshold == 7
    assert received_input.dry_run is True
    assert received_input.recover is True


def test_session_clean_overexposed_ir_reports_session_process_errors(cli_runner, monkeypatch):
    def fail_run(input_data):
        raise SessionProcessError("Symbolic links are not supported: /session/init/image.jpg")

    monkeypatch.setattr("wv.cli.commands.session.run_clean_overexposed_ir", fail_run)

    result = cli_runner.invoke(
        app, ["session", "clean", "overexposed-ir", "session-1"]
    )

    assert result.exit_code == 1
    assert "Symbolic links are not supported" in result.output
    assert "Invalid value for 'SESSION_ID'" not in result.output


def test_session_clean_bursts_reports_session_process_errors(cli_runner, monkeypatch):
    def fail_run(input_data):
        raise SessionProcessError("Symbolic links are not supported: /session/init/image.jpg")

    monkeypatch.setattr("wv.cli.commands.session.run_clean_bursts", fail_run)

    result = cli_runner.invoke(app, ["session", "clean", "bursts", "session-1"])

    assert result.exit_code == 1
    assert "Symbolic links are not supported" in result.output
    assert "Invalid value for 'SESSION_ID'" not in result.output


def test_session_detect_content_forwards_options(cli_runner, monkeypatch):
    received_input = None

    def fake_run(input_data):
        nonlocal received_input
        received_input = input_data
        return SessionDetectContentResult(
            session_id=input_data.session_id,
            process=None,
            files_evaluated=1,
            files_animal=1,
        )

    monkeypatch.setattr("wv.cli.commands.session.run_detect_content", fake_run)

    result = cli_runner.invoke(
        app,
        [
            "session",
            "detect",
            "content",
            "session-1",
            "--model",
            "custom.pt",
            "--confidence-threshold",
            "0.7",
            "--ambiguity-gap",
            "0.2",
            "--batch-size",
            "4",
            "--dry-run",
            "--recover",
        ],
    )

    assert result.exit_code == 0
    assert received_input.model == "custom.pt"
    assert received_input.confidence_threshold == 0.7
    assert received_input.ambiguity_gap == 0.2
    assert received_input.batch_size == 4
    assert received_input.dry_run is True
    assert received_input.recover is True
