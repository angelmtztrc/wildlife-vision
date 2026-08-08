from pathlib import Path

import platformdirs

from wv.cli.commands import config
from wv.workspace.schema import get_known_keys


def test_config_key_completion_returns_known_keys():
    completions = config._complete_key("workspace.")

    assert "workspace.version" in completions
    assert completions == [key for key in get_known_keys() if key.startswith("workspace.")]


def test_config_init_rejects_existing_workspace_config(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    from wv.cli.commands import workspace

    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text("workspace:\n  version: 999\n", encoding="utf-8")

    result = cli_runner.invoke(config.app, ["init"])

    assert result.exit_code == 1
    assert "Workspace config already" in result.output
    assert "exists" in result.output
    assert "version: 999" in config_file.read_text(encoding="utf-8")


def test_config_get_prints_known_value(cli_runner, tmp_path: Path, monkeypatch):
    from wv.cli.commands import workspace

    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(config.app, ["get", "workspace.version"])

    assert result.exit_code == 0
    assert result.output.strip() == "2"


def test_config_set_rejects_unknown_key(cli_runner, tmp_path: Path, monkeypatch):
    from wv.cli.commands import workspace

    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(config.app, ["set", "custom.unknown", "true"])

    assert result.exit_code == 1
    assert "Unknown workspace config key" in result.output


def test_config_reset_restores_default(cli_runner, tmp_path: Path, monkeypatch):
    from wv.cli.commands import workspace

    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(config.app, ["reset", "database.path"])

    assert result.exit_code == 0
    assert "Reset" in result.output
    assert "database.path=" in result.output


def test_config_validate_ignores_unknown_keys(cli_runner, tmp_path: Path, monkeypatch):
    from wv.cli.commands import workspace

    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8") + "custom:\n  unknown: true\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(config.app, ["validate"])

    assert result.exit_code == 0
    assert "Workspace config is valid" in result.output


def test_config_path_prints_workspace_config_path(cli_runner, tmp_path: Path, monkeypatch):
    from wv.cli.commands import workspace

    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(config.app, ["path"])

    assert result.exit_code == 0
    assert result.output.strip() == str(workspace_path / ".wv" / "config.yml")
