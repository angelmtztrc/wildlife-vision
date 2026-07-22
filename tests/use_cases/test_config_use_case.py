from pathlib import Path

import platformdirs
import pytest

from wv.use_cases.config import run_get, run_init, run_path, run_reset, run_set, run_validate
from wv.use_cases.workspace import WorkspaceInitInput, run_init as run_workspace_init
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import load_workspace_config


def test_run_init_overwrites_existing_workspace_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text("workspace:\n  version: 999\n")

    result = run_init()

    assert result.path == config_file
    assert load_workspace_config(config_file)["workspace"]["version"] == 1


def test_run_get_returns_known_config_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    result = run_get("workspace.version")

    assert result.value == 1


def test_run_set_updates_known_value_and_preserves_unknown_keys(
    tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text() + "custom:\n  unknown: true\n",
        encoding="utf-8",
    )

    result = run_set("workspace.version", "1")
    value = load_workspace_config(config_file)

    assert result.value == 1
    assert value["custom"]["unknown"] is True


def test_run_set_rejects_unknown_key(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    with pytest.raises(WorkspaceError, match="Unknown workspace config key"):
        run_set("custom.unknown", "true")


def test_run_reset_restores_default_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    result = run_reset("database.path")

    assert result.value == str((workspace_path / ".wv" / "database.sqlite").resolve())


def test_run_validate_ignores_unknown_keys(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text() + "custom:\n  unknown: value\n",
        encoding="utf-8",
    )

    result = run_validate()

    assert result.path == config_file


def test_run_validate_rejects_invalid_required_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        (
            "workspace:\n"
            "  version: 1\n"
            "  path: relative/path\n"
            "database:\n"
            f"  path: {workspace_path / '.wv' / 'database.sqlite'}\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkspaceError, match="workspace.path"):
        run_validate()


def test_run_path_returns_workspace_config_path(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    result = run_path()

    assert result.path == workspace_path / ".wv" / "config.yml"
