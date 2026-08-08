from pathlib import Path

import pytest

import wv.cli.commands.gui as gui_command
from wv.cli.main import app


def test_gui_review_detection_help_lists_detection_option(cli_runner):
    result = cli_runner.invoke(app, ["gui", "review-detection", "--help"])

    assert result.exit_code == 0
    assert "--detection" in result.output
    assert "--pending-only" in result.output


def test_gui_review_detection_launches_application(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        gui_command,
        "launch_review_detection_app",
        lambda session_id, detection_label, pending_only: calls.append(
            (session_id, detection_label, pending_only)
        ),
    )

    result = cli_runner.invoke(
        app,
        ["gui", "review-detection", "SESSION001", "--detection", "animal", "--pending-only"],
    )

    assert result.exit_code == 0
    assert calls == [("SESSION001", "animal", True)]


def test_gui_review_detection_rejects_unknown_detection_label(cli_runner):
    result = cli_runner.invoke(
        app,
        ["gui", "review-detection", "SESSION001", "--detection", "bird"],
    )

    assert result.exit_code != 0
    assert "Unknown detection label 'bird'" in result.output


def test_gui_favorites_help_lists_pending_only(cli_runner):
    result = cli_runner.invoke(app, ["gui", "favorites", "--help"])

    assert result.exit_code == 0
    assert "--pending-only" in result.output


def test_gui_favorites_launches_application(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        gui_command,
        "launch_favorites_app",
        lambda session_id, pending_only: calls.append((session_id, pending_only)),
    )

    result = cli_runner.invoke(
        app,
        ["gui", "favorites", "SESSION001", "--pending-only"],
    )

    assert result.exit_code == 0
    assert calls == [("SESSION001", True)]
