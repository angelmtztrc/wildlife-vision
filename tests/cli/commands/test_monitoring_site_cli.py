from pathlib import Path

import platformdirs

from wv.cli.commands import monitoring_site, workspace


def test_monitoring_site_create_succeeds(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(
        monitoring_site.app,
        [
            "create",
            "SITE001",
            "--name",
            "North Ridge",
            "--description",
            "Pine clearing",
            "--latitude",
            "31.2",
        ],
    )

    assert result.exit_code == 0
    assert "Monitoring site created" in result.output
    assert "SITE001" in result.output


def test_monitoring_site_create_rejects_duplicate_id(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE001", "--name", "North Ridge"])

    result = cli_runner.invoke(
        monitoring_site.app,
        ["create", "SITE001", "--name", "Second Name"],
    )

    assert result.exit_code == 1
    assert "already" in result.output.lower()
    assert "exists" in result.output.lower()


def test_monitoring_site_list_prints_rows(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE002", "--name", "Beta"])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE001", "--name", "Alpha"])

    result = cli_runner.invoke(monitoring_site.app, ["list"])

    assert result.exit_code == 0
    assert result.output.strip().splitlines() == ["SITE001\tAlpha", "SITE002\tBeta"]


def test_monitoring_site_show_prints_site_fields(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(
        monitoring_site.app,
        [
            "create",
            "SITE001",
            "--name",
            "North Ridge",
            "--description",
            "Pine clearing",
            "--latitude",
            "31.2",
            "--longitude",
            "-110.9",
            "--elevation",
            "1250",
            "--notes",
            "Summer",
        ],
    )

    result = cli_runner.invoke(monitoring_site.app, ["show", "SITE001"])

    assert result.exit_code == 0
    assert result.output.strip().splitlines() == [
        "id: SITE001",
        "name: North Ridge",
        "description: Pine clearing",
        "latitude: 31.2",
        "longitude: -110.9",
        "elevation: 1250.0",
        "notes: Summer",
    ]


def test_monitoring_site_show_rejects_missing_id(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(monitoring_site.app, ["show", "MISSING"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_monitoring_site_update_applies_partial_changes(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(
        monitoring_site.app,
        [
            "create",
            "SITE001",
            "--name",
            "North Ridge",
            "--description",
            "Initial",
            "--notes",
            "Existing notes",
        ],
    )

    result = cli_runner.invoke(
        monitoring_site.app,
        ["update", "SITE001", "--name", "South Ridge", "--latitude", "31.2"],
    )

    assert result.exit_code == 0
    assert "Monitoring site updated" in result.output

    show_result = cli_runner.invoke(monitoring_site.app, ["show", "SITE001"])
    assert show_result.output.strip().splitlines() == [
        "id: SITE001",
        "name: South Ridge",
        "description: Initial",
        "latitude: 31.2",
        "longitude: ",
        "elevation: ",
        "notes: Existing notes",
    ]


def test_monitoring_site_update_requires_at_least_one_field(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE001", "--name", "North Ridge"])

    result = cli_runner.invoke(monitoring_site.app, ["update", "SITE001"])

    assert result.exit_code == 1
    assert "At least one field" in result.output
