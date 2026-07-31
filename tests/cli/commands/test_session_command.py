from pathlib import Path

from wv.cli.main import app
from wv.use_cases.clean.corrupted import CleanCorruptedResult
from wv.use_cases.session.clean_corrupted import SessionCleanCorruptedResult


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
