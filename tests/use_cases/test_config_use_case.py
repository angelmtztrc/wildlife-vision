from pathlib import Path

import platformdirs
import pytest

from wv.use_cases.config.get_value import GetConfigValueInput, run as run_get
from wv.use_cases.config.initialize import ConfigInitializeInput, run as run_initialize
from wv.use_cases.config.list import ListConfigInput, run as run_list
from wv.use_cases.config.reset_value import ResetConfigValueInput, run as run_reset
from wv.use_cases.config.set_value import SetConfigValueInput, run as run_set
from wv.use_cases.config.show_path import ShowConfigPathInput, run as run_show_path
from wv.use_cases.config.validate import ValidateConfigInput, run as run_validate
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_workspace_initialize,
)
from wv.workspace.common import WorkspaceError
from wv.workspace.schema import get_known_keys
from wv.workspace.workspace_config import load_workspace_config


def test_run_init_rejects_existing_workspace_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text("workspace:\n  version: 999\n")

    with pytest.raises(WorkspaceError, match="already exists"):
        run_initialize(ConfigInitializeInput())
    assert load_workspace_config(config_file)["workspace"]["version"] == 999


def test_run_get_returns_known_config_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    result = run_get(GetConfigValueInput(key="workspace.version"))

    assert result.value == 2


def test_run_list_returns_known_config_values_in_schema_order(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8") + "custom:\n  unknown: value\n",
        encoding="utf-8",
    )

    result = run_list(ListConfigInput())

    assert [item.key for item in result.items] == get_known_keys()
    assert result.items[0].value == 2
    assert result.items[-1].value == 4


def test_run_list_rejects_version_one_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text(encoding="utf-8").replace("version: 2", "version: 1"),
        encoding="utf-8",
    )

    with pytest.raises(WorkspaceError, match="wv workspace migrate"):
        run_list(ListConfigInput())


def test_run_set_updates_known_value_and_preserves_unknown_keys(
    tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text() + "custom:\n  unknown: true\n",
        encoding="utf-8",
    )

    result = run_set(SetConfigValueInput(key="workspace.version", raw_value="1"))
    value = load_workspace_config(config_file)

    assert result.value == 1
    assert value["custom"]["unknown"] is True


def test_run_set_rejects_unknown_key(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    with pytest.raises(WorkspaceError, match="Unknown workspace config key"):
        run_set(SetConfigValueInput(key="custom.unknown", raw_value="true"))


def test_run_reset_restores_default_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    result = run_reset(ResetConfigValueInput(key="database.path"))

    assert result.value == str((workspace_path / ".wv" / "database.sqlite").resolve())


def test_run_validate_ignores_unknown_keys(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    config_file = workspace_path / ".wv" / "config.yml"
    config_file.write_text(
        config_file.read_text() + "custom:\n  unknown: value\n",
        encoding="utf-8",
    )

    result = run_validate(ValidateConfigInput())

    assert result.path == config_file


def test_run_validate_rejects_invalid_required_value(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
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
        run_validate(ValidateConfigInput())


def test_run_path_returns_workspace_config_path(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    result = run_show_path(ShowConfigPathInput())

    assert result.path == workspace_path / ".wv" / "config.yml"
