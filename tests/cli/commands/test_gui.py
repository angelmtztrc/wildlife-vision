from pathlib import Path

import pytest

import wv.cli.commands.gui as gui_command
from wv.cli.main import app


def test_gui_review_help_lists_detection_option(cli_runner):
    result = cli_runner.invoke(app, ["gui", "review", "--help"])

    assert result.exit_code == 0
    assert "--detection" in result.output
    assert "--pending-only" in result.output


def test_gui_review_launches_application(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[Path, str, bool]] = []

    monkeypatch.setattr(
        gui_command,
        "launch_review_app",
        lambda session_path, detection_label, pending_only: calls.append(
            (session_path, detection_label, pending_only)
        ),
    )

    result = cli_runner.invoke(
        app,
        ["gui", "review", str(tmp_path), "--detection", "animal", "--pending-only"],
    )

    assert result.exit_code == 0
    assert calls == [(tmp_path, "animal", True)]


def test_gui_review_rejects_unknown_detection_label(cli_runner, tmp_path: Path):
    result = cli_runner.invoke(
        app,
        ["gui", "review", str(tmp_path), "--detection", "bird"],
    )

    assert result.exit_code != 0
    assert "Unknown detection label 'bird'" in result.output
