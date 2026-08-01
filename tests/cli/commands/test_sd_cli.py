from pathlib import Path

import platformdirs

from wv.cli.commands import device, monitoring_site, sd, workspace


def _setup_workspace(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(device.app, ["create", "HNT001", "--name", "North Camera"])
    cli_runner.invoke(device.app, ["create", "HNT002", "--name", "South Camera"])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE001", "--name", "North Ridge"])
    cli_runner.invoke(monitoring_site.app, ["create", "SITE002", "--name", "South Ridge"])
    return workspace_path


def test_sd_init_succeeds(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()

    result = cli_runner.invoke(
        sd.app,
        ["init", str(sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    assert result.exit_code == 0
    assert "SD initialized" in result.output
    assert (sd_path / ".wv" / "config.yml").is_file()


def test_sd_init_rejects_already_assigned_device(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    first_sd_path = tmp_path / "sd-card-1"
    second_sd_path = tmp_path / "sd-card-2"
    first_sd_path.mkdir()
    second_sd_path.mkdir()
    cli_runner.invoke(
        sd.app,
        ["init", str(first_sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    result = cli_runner.invoke(
        sd.app,
        ["init", str(second_sd_path), "--device", "HNT001", "--monitoring-site", "SITE002"],
    )

    assert result.exit_code == 1
    assert "wv sd update" in result.output


def test_sd_init_rejects_symlinked_root(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    sd_link = tmp_path / "sd-link"
    sd_link.symlink_to(sd_path, target_is_directory=True)

    result = cli_runner.invoke(
        sd.app,
        ["init", str(sd_link), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    assert result.exit_code == 1
    assert "Symbolic links are not supported" in result.output


def test_sd_show_prints_config(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    cli_runner.invoke(
        sd.app,
        ["init", str(sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    result = cli_runner.invoke(sd.app, ["show", str(sd_path)])

    assert result.exit_code == 0
    assert "device_id: HNT001" in result.output
    assert "monitoring_site_id: SITE001" in result.output


def test_sd_update_switches_assignment(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    cli_runner.invoke(
        sd.app,
        ["init", str(sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    result = cli_runner.invoke(
        sd.app,
        ["update", str(sd_path), "--device", "HNT002", "--monitoring-site", "SITE002"],
    )

    assert result.exit_code == 0
    assert "SD updated" in result.output


def test_sd_clear_removes_config(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    cli_runner.invoke(
        sd.app,
        ["init", str(sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    result = cli_runner.invoke(sd.app, ["clear", str(sd_path)])

    assert result.exit_code == 0
    assert "SD cleared" in result.output
    assert not (sd_path / ".wv" / "config.yml").exists()


def test_sd_sync_reports_already_synchronized_card(cli_runner, tmp_path: Path, monkeypatch):
    _setup_workspace(cli_runner, tmp_path, monkeypatch)
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    cli_runner.invoke(
        sd.app,
        ["init", str(sd_path), "--device", "HNT001", "--monitoring-site", "SITE001"],
    )

    result = cli_runner.invoke(sd.app, ["sync", str(sd_path)])

    assert result.exit_code == 0
    assert "already matches SD config" in result.output
