from pathlib import Path

import platformdirs

from wv.cli.commands import workspace


def test_workspace_init_creates_workspace(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    result = cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    assert result.exit_code == 0
    assert "[DONE]" in result.output
    assert "Workspace initialized" in result.output
    assert (workspace_path / ".wv" / "database.sqlite").exists()


def test_workspace_init_rejects_existing_workspace(
    cli_runner, tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    (workspace_path / ".wv").mkdir(parents=True)
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    result = cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_workspace_show_reports_configuration(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(workspace.app, ["show"])

    assert result.exit_code == 0
    assert f"workspace_path: {workspace_path.resolve()}" in result.output
    assert "sessions: True" in result.output
    assert "database: True" in result.output


def test_workspace_show_reports_not_configured(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    result = cli_runner.invoke(workspace.app, ["show"])

    assert result.exit_code == 0
    assert "workspace_path: not configured" in result.output


def test_workspace_validate_succeeds(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(workspace.app, ["validate"])

    assert result.exit_code == 0
    assert "Workspace is valid" in result.output


def test_workspace_validate_fails_for_invalid_structure(
    cli_runner, tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    (workspace_path / "exports").rmdir()

    result = cli_runner.invoke(workspace.app, ["validate"])

    assert result.exit_code == 1
    assert "validation failed" in result.output.lower()
    assert "exports" in result.output
