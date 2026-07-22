from pathlib import Path

import platformdirs
import pytest

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.use_cases.device import DeviceInput, DeviceUpdateInput
from wv.use_cases.device import run_create, run_list, run_show, run_update
from wv.use_cases.workspace import WorkspaceInitInput, run_init as run_workspace_init
from wv.workspace.common import WorkspaceError


def test_run_create_requires_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        run_create(DeviceInput(id="HNT001", name="North Camera"))


def test_run_create_and_show_return_device(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    created = run_create(
        DeviceInput(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            serial_number="SN-001",
            notes="Primary unit",
        )
    )

    shown = run_show("HNT001")

    assert shown == created


def test_run_create_rejects_duplicate_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(DeviceInput(id="HNT001", name="North Camera"))

    with pytest.raises(RecordAlreadyExistsError, match="HNT001"):
        run_create(DeviceInput(id="HNT001", name="Second Name"))


def test_run_list_returns_rows_ordered_by_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(DeviceInput(id="HNT002", name="Beta"))
    run_create(DeviceInput(id="HNT001", name="Alpha"))

    result = run_list()

    assert [device.id for device in result] == ["HNT001", "HNT002"]


def test_run_show_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    with pytest.raises(RecordNotFoundError, match="MISSING"):
        run_show("MISSING")


def test_run_update_rejects_empty_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(DeviceInput(id="HNT001", name="North Camera"))

    with pytest.raises(WorkspaceError, match="At least one field"):
        run_update(DeviceUpdateInput(id="HNT001"))


def test_run_update_applies_partial_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(
        DeviceInput(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            notes="Existing notes",
        )
    )

    result = run_update(
        DeviceUpdateInput(
            id="HNT001",
            name="South Camera",
            serial_number="SN-002",
        )
    )

    assert result.id == "HNT001"
    assert result.name == "South Camera"
    assert result.manufacturer == "Browning"
    assert result.serial_number == "SN-002"
    assert result.notes == "Existing notes"


def test_run_update_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    with pytest.raises(RecordNotFoundError, match="MISSING"):
        run_update(DeviceUpdateInput(id="MISSING", name="Updated"))
