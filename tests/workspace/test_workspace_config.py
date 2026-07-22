from pathlib import Path

import platformdirs
import pytest

from wv.workspace import config
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import (
    get_config_property,
    initialize_workspace_config,
    load_workspace_config,
    reset_config_property,
    set_config_property,
    validate_known_key,
    validate_workspace_config,
)


def test_get_global_config_file_uses_platformdirs(
    tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    assert config.get_global_config_file() == config_dir / "config.yml"


def test_write_and_load_global_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    written_file = config.write_global_config(
        {"workspace": {"path": str(tmp_path / "workspace")}}
    )

    assert written_file == config_dir / "config.yml"
    assert config.load_global_config() == {
        "workspace": {"path": str(tmp_path / "workspace")}
    }


def test_get_workspace_path_returns_none_for_missing_config(
    tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    assert config.get_workspace_path() is None


def test_get_workspace_path_returns_resolved_path(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    config.write_global_config({"workspace": {"path": str(workspace_path)}})

    assert config.get_workspace_path() == workspace_path.resolve()


def test_initialize_workspace_config_writes_expected_defaults(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    config_file = workspace_path / ".wv" / "config.yml"

    written_path = initialize_workspace_config(workspace_path, config_file=config_file)

    assert written_path == config_file
    assert load_workspace_config(config_file) == {
        "workspace": {
            "version": 1,
            "path": str(workspace_path.resolve()),
        },
        "database": {
            "path": str((workspace_path / ".wv" / "database.sqlite").resolve()),
        },
    }


def test_set_and_reset_config_property_preserves_unknown_keys(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    value = {
        "workspace": {"version": 1, "path": str(workspace_path.resolve())},
        "database": {"path": str((workspace_path / ".wv" / "database.sqlite").resolve())},
        "custom": {"unknown": True},
    }

    updated_value = set_config_property(value, "workspace.version", 2)
    reset_value = reset_config_property(updated_value, "workspace.version", workspace_path)

    assert get_config_property(reset_value, "workspace.version") == 1
    assert get_config_property(reset_value, "custom.unknown") is True


def test_validate_workspace_config_ignores_unknown_keys(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    value = {
        "workspace": {"version": 1, "path": str(workspace_path.resolve())},
        "database": {"path": str((workspace_path / ".wv" / "database.sqlite").resolve())},
        "custom": {"unknown": "value"},
    }

    validate_workspace_config(value, workspace_path)


def test_validate_workspace_config_rejects_missing_required_key(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    value = {
        "workspace": {"version": 1, "path": str(workspace_path.resolve())},
    }

    with pytest.raises(WorkspaceError, match="database.path"):
        validate_workspace_config(value, workspace_path)


def test_validate_known_key_rejects_unknown_key():
    with pytest.raises(WorkspaceError, match="Unknown workspace config key"):
        validate_known_key("custom.unknown")
