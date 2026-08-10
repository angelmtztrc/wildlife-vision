from pathlib import Path

import pytest

import wv.cli.commands.gui as gui_command
from wv.cli.main import app
from wv.use_cases.session._shared import SessionError
from wv.use_cases.session.list import ListSessionsResult, SessionListItem


def _session(session_id: str) -> SessionListItem:
    return SessionListItem(
        id=session_id,
        started_at="2026-08-01T12:00:00+00:00",
        monitoring_site_id="SITE001",
        ingest_status="completed",
        processing_status="completed",
        next_action=None,
        next_process=None,
    )


def test_gui_session_completion_uses_reviewable_sessions(monkeypatch):
    received = None

    def fake_run(input_data):
        nonlocal received
        received = input_data
        return ListSessionsResult(items=[_session("20260808_120000__SITE001")])

    monkeypatch.setattr("wv.cli.completion.run_list_sessions", fake_run)

    assert gui_command.complete_reviewable_session_id("20260808") == [
        "20260808_120000__SITE001"
    ]
    assert received.completed_detection_only is True


def test_gui_session_completion_returns_no_suggestions_on_session_error(monkeypatch):
    monkeypatch.setattr(
        "wv.cli.completion.run_list_sessions",
        lambda input_data: (_ for _ in ()).throw(SessionError("No workspace configured.")),
    )

    assert gui_command.complete_reviewable_session_id("") == []


def test_gui_detection_completion_filters_expected_labels_case_insensitively():
    assert gui_command.complete_detection_label("") == [
        "animal",
        "vehicle",
        "human",
        "domestic",
        "other",
        "empty",
    ]
    assert gui_command.complete_detection_label("DO") == ["domestic"]


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
