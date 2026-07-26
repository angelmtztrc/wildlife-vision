from pathlib import Path

import platformdirs
import pytest

from wv.use_cases.device._shared import DeviceError
from wv.use_cases.device.create import CreateDeviceInput, run as run_create
from wv.use_cases.device.list import ListDevicesInput, run as run_list
from wv.use_cases.device.show import ShowDeviceInput, run as run_show
from wv.use_cases.device.update import UpdateDeviceInput, run as run_update
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_workspace_initialize,
)
from wv.workspace.common import WorkspaceError


def test_run_create_requires_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        run_create(CreateDeviceInput(id="HNT001", name="North Camera"))


def test_run_create_and_show_return_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    created = run_create(
        CreateDeviceInput(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            serial_number="SN-001",
            notes="Primary unit",
        )
    )

    shown = run_show(ShowDeviceInput(id="HNT001"))

    assert shown.device == created.device


def test_run_create_rejects_duplicate_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateDeviceInput(id="HNT001", name="North Camera"))

    with pytest.raises(DeviceError, match="HNT001"):
        run_create(CreateDeviceInput(id="HNT001", name="Second Name"))


def test_run_list_returns_rows_ordered_by_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateDeviceInput(id="HNT002", name="Beta"))
    run_create(CreateDeviceInput(id="HNT001", name="Alpha"))

    result = run_list(ListDevicesInput())

    assert [device.id for device in result.items] == ["HNT001", "HNT002"]


def test_run_show_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    with pytest.raises(DeviceError, match="MISSING"):
        run_show(ShowDeviceInput(id="MISSING"))


def test_run_update_rejects_empty_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateDeviceInput(id="HNT001", name="North Camera"))

    with pytest.raises(WorkspaceError, match="At least one field"):
        run_update(UpdateDeviceInput(id="HNT001"))


def test_run_update_applies_partial_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(
        CreateDeviceInput(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            notes="Existing notes",
        )
    )

    result = run_update(
        UpdateDeviceInput(
            id="HNT001",
            name="South Camera",
            serial_number="SN-002",
        )
    )

    assert result.device.id == "HNT001"
    assert result.device.name == "South Camera"
    assert result.device.manufacturer == "Browning"
    assert result.device.serial_number == "SN-002"
    assert result.device.notes == "Existing notes"


def test_run_update_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    with pytest.raises(DeviceError, match="MISSING"):
        run_update(UpdateDeviceInput(id="MISSING", name="Updated"))
