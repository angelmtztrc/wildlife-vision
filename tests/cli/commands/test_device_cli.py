from pathlib import Path

import platformdirs

from wv.cli.commands import device, workspace


def test_device_create_succeeds(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(
        device.app,
        [
            "create",
            "HNT001",
            "--name",
            "North Camera",
            "--manufacturer",
            "Browning",
            "--serial-number",
            "SN-001",
        ],
    )

    assert result.exit_code == 0
    assert "Device created" in result.output
    assert "HNT001" in result.output


def test_device_create_rejects_duplicate_id(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(device.app, ["create", "HNT001", "--name", "North Camera"])

    result = cli_runner.invoke(
        device.app,
        ["create", "HNT001", "--name", "Second Name"],
    )

    assert result.exit_code == 1
    assert "already" in result.output.lower()
    assert "exists" in result.output.lower()


def test_device_list_prints_rows(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(device.app, ["create", "HNT002", "--name", "Beta"])
    cli_runner.invoke(device.app, ["create", "HNT001", "--name", "Alpha"])

    result = cli_runner.invoke(device.app, ["list"])

    assert result.exit_code == 0
    assert result.output.strip().splitlines() == ["HNT001\tAlpha", "HNT002\tBeta"]


def test_device_show_prints_device_fields(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(
        device.app,
        [
            "create",
            "HNT001",
            "--name",
            "North Camera",
            "--manufacturer",
            "Browning",
            "--serial-number",
            "SN-001",
            "--notes",
            "Primary unit",
        ],
    )

    result = cli_runner.invoke(device.app, ["show", "HNT001"])

    assert result.exit_code == 0
    assert result.output.strip().splitlines() == [
        "id: HNT001",
        "name: North Camera",
        "manufacturer: Browning",
        "serial_number: SN-001",
        "notes: Primary unit",
    ]


def test_device_show_rejects_missing_id(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])

    result = cli_runner.invoke(device.app, ["show", "MISSING"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_device_update_applies_partial_changes(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(
        device.app,
        [
            "create",
            "HNT001",
            "--name",
            "North Camera",
            "--manufacturer",
            "Browning",
            "--notes",
            "Existing notes",
        ],
    )

    result = cli_runner.invoke(
        device.app,
        ["update", "HNT001", "--name", "South Camera", "--serial-number", "SN-002"],
    )

    assert result.exit_code == 0
    assert "Device updated" in result.output

    show_result = cli_runner.invoke(device.app, ["show", "HNT001"])
    assert show_result.output.strip().splitlines() == [
        "id: HNT001",
        "name: South Camera",
        "manufacturer: Browning",
        "serial_number: SN-002",
        "notes: Existing notes",
    ]


def test_device_update_requires_at_least_one_field(cli_runner, tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    cli_runner.invoke(workspace.app, ["init", str(workspace_path)])
    cli_runner.invoke(device.app, ["create", "HNT001", "--name", "North Camera"])

    result = cli_runner.invoke(device.app, ["update", "HNT001"])

    assert result.exit_code == 1
    assert "At least one field" in result.output
