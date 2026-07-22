from pathlib import Path

import platformdirs

from wv.workspace import config


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
