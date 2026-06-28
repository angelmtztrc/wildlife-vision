from pathlib import Path

import pytest

import wv.config as config


def test_load_reads_yaml_from_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / "setup.yml"
    config_file.write_text("paths:\n  root: ./data\n")
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    config.load.cache_clear()

    assert config.load() == {"paths": {"root": "./data"}}


def test_get_property_returns_nested_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "load", lambda: {"paths": {"root": "./data"}})

    assert config.get_property("paths.root") == "./data"


def test_get_property_returns_default_for_missing_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "load", lambda: {"paths": {}})

    assert config.get_property("paths.root", "./fallback") == "./fallback"


def test_get_property_returns_default_when_intermediate_value_is_not_mapping(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(config, "load", lambda: {"paths": "not-a-dict"})

    assert config.get_property("paths.root", "./fallback") == "./fallback"


def test_get_repo_root_walks_parent_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = tmp_path / "repo"
    config_dir = repo_root / "src" / "wv" / "config"
    config_dir.mkdir(parents=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'wildlife-vision'\n")
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    config.get_repo_root.cache_clear()

    assert config.get_repo_root() == repo_root


def test_get_root_path_resolves_relative_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setattr(config, "get_property", lambda key, default=None: "./data")
    monkeypatch.setattr(config, "get_repo_root", lambda: repo_root)

    assert config.get_root_path() == repo_root / "data"


def test_get_root_path_keeps_absolute_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    absolute_root = tmp_path / "data"
    monkeypatch.setattr(
        config, "get_property", lambda key, default=None: str(absolute_root)
    )

    assert config.get_root_path() == absolute_root


def test_get_root_path_requires_string_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(config, "get_property", lambda key, default=None: 123)

    with pytest.raises(TypeError):
        config.get_root_path()


def test_get_device_ids_reads_project_config():
    assert config.get_device_ids() == ["HNT001", "HNT002", "HNT003"]


def test_get_monitoring_sites_ids_reads_project_config():
    assert config.get_monitoring_sites_ids() == [
        "GF_STREAM_FEEDER",
        "GF_STREAM_DRINK_ZONE",
        "GF_RIVER_OAKS_FOREST",
        "CASCABEL_RIVERSIDE",
    ]
