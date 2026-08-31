from pathlib import Path

import platformdirs
from alembic import command
from alembic.config import Config

from wv.cli.commands import workspace
from wv.persistence.alembic import get_alembic_directory
from wv.persistence.sql_session import build_database_url


def _downgrade_database(database_path: Path) -> None:
    config = Config()
    config.set_main_option("script_location", str(get_alembic_directory()))
    config.set_main_option("sqlalchemy.url", build_database_url(database_path))
    command.downgrade(config, "0003_session_processes")


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


def test_workspace_activate_switches_active_workspace(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_a)])
    cli_runner.invoke(workspace.app, ["init", str(workspace_b)])

    result = cli_runner.invoke(workspace.app, ["activate", str(workspace_a)])
    show_result = cli_runner.invoke(workspace.app, ["show"])

    assert result.exit_code == 0
    assert "Workspace activated" in result.output
    assert f"workspace_path: {workspace_a.resolve()}" in show_result.output


def test_workspace_activate_failure_keeps_previous_workspace_active(
    cli_runner, tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    active_workspace_path = tmp_path / "active-workspace"
    candidate_path = tmp_path / "candidate"
    active_workspace_path.mkdir()
    candidate_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(active_workspace_path)])

    result = cli_runner.invoke(workspace.app, ["activate", str(candidate_path)])
    show_result = cli_runner.invoke(workspace.app, ["show"])

    assert result.exit_code == 1
    assert "Workspace activation failed" in result.output
    assert f"workspace_path: {active_workspace_path.resolve()}" in show_result.output


def test_workspace_init_rejects_symlinked_root(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    workspace_link = tmp_path / "workspace-link"
    workspace_link.symlink_to(workspace_path, target_is_directory=True)
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    result = cli_runner.invoke(workspace.app, ["init", str(workspace_link)])

    assert result.exit_code == 1
    assert "Workspace initialization failed" in result.output


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


def test_workspace_migrate_upgrades_active_database(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    _downgrade_database(workspace_path / ".wv" / "database.sqlite")

    result = cli_runner.invoke(workspace.app, ["migrate"])

    assert result.exit_code == 0
    assert "Workspace migrated" in result.output
    assert "0003_session_processes" in result.output


def test_workspace_migrate_reports_current_database(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(workspace.app, ["migrate"])

    assert result.exit_code == 0
    assert "already up to date" in result.output


def test_workspace_migrate_rejects_missing_database(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    database_path = workspace_path / ".wv" / "database.sqlite"
    database_path.unlink()

    result = cli_runner.invoke(workspace.app, ["migrate"])

    assert result.exit_code == 1
    assert "Workspace migration failed" in result.output
    assert database_path.exists() is False
