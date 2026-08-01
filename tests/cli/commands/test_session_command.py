from pathlib import Path

from wv.cli.main import app
from wv.use_cases.clean.corrupted import CleanCorruptedResult
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedResult
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrResult
from wv.use_cases.session.clean_overexposed_ir import (
    SessionCleanOverexposedIrResult,
)
from wv.use_cases.clean.bursts import CleanBurstsResult
from wv.use_cases.session.clean_bursts import SessionCleanBurstsResult


def test_session_clean_corrupted_prints_summary(cli_runner, monkeypatch):
    def fake_run(input_data):
        return SessionCleanCorruptedResult(
            session_id=input_data.session_id,
            process=None,
            clean_result=CleanCorruptedResult(
                files_corrupted=1,
                files_moved=1,
                destination=Path("ignored/corrupted"),
            ),
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
            clean_result=CleanOverexposedIrResult(
                files_processed=2,
                files_overexposed=1,
                files_moved=1,
                destination=Path("ignored/overexposed"),
            ),
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
            "--ptc-high-threshold",
            "0.75",
            "--dry-run",
            "--recover",
        ],
    )

    assert result.exit_code == 0
    assert received_input.mean_threshold == 210.0
    assert received_input.std_threshold == 20.0
    assert received_input.high_level == 225
    assert received_input.ptc_high_threshold == 0.75
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
            clean_result=CleanOverexposedIrResult(files_failed=1),
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
            clean_result=CleanBurstsResult(files_bursts=1, files_reduced=2, files_moved=2),
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
