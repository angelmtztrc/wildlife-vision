from pathlib import Path

import platformdirs
import pytest

from wv.use_cases.monitoring_site._shared import MonitoringSiteError
from wv.use_cases.monitoring_site.create import CreateMonitoringSiteInput, run as run_create
from wv.use_cases.monitoring_site.list import ListMonitoringSitesInput, run as run_list
from wv.use_cases.monitoring_site.show import ShowMonitoringSiteInput, run as run_show
from wv.use_cases.monitoring_site.update import UpdateMonitoringSiteInput, run as run_update
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_workspace_initialize,
)
from wv.workspace.common import WorkspaceError


def test_run_create_requires_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        run_create(CreateMonitoringSiteInput(id="SITE001", name="North Ridge"))


def test_run_create_and_show_return_monitoring_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    created = run_create(
        CreateMonitoringSiteInput(
            id="SITE001",
            name="North Ridge",
            description="Pine clearing",
            latitude=31.2,
            longitude=-110.9,
            elevation=1250.0,
            notes="Summer",
        )
    )

    shown = run_show(ShowMonitoringSiteInput(id="SITE001"))

    assert shown.monitoring_site == created.monitoring_site


def test_run_create_rejects_duplicate_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateMonitoringSiteInput(id="SITE001", name="North Ridge"))

    with pytest.raises(MonitoringSiteError, match="SITE001"):
        run_create(CreateMonitoringSiteInput(id="SITE001", name="Second Name"))


def test_run_list_returns_rows_ordered_by_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateMonitoringSiteInput(id="SITE002", name="Beta"))
    run_create(CreateMonitoringSiteInput(id="SITE001", name="Alpha"))

    result = run_list(ListMonitoringSitesInput())

    assert [site.id for site in result.items] == ["SITE001", "SITE002"]


def test_run_show_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    with pytest.raises(MonitoringSiteError, match="MISSING"):
        run_show(ShowMonitoringSiteInput(id="MISSING"))


def test_run_update_rejects_empty_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(CreateMonitoringSiteInput(id="SITE001", name="North Ridge"))

    with pytest.raises(WorkspaceError, match="At least one field"):
        run_update(UpdateMonitoringSiteInput(id="SITE001"))


def test_run_update_applies_partial_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create(
        CreateMonitoringSiteInput(
            id="SITE001",
            name="North Ridge",
            description="Initial",
            notes="Existing notes",
        )
    )

    result = run_update(
        UpdateMonitoringSiteInput(
            id="SITE001",
            name="South Ridge",
            latitude=31.2,
        )
    )

    assert result.monitoring_site.id == "SITE001"
    assert result.monitoring_site.name == "South Ridge"
    assert result.monitoring_site.description == "Initial"
    assert result.monitoring_site.latitude == 31.2
    assert result.monitoring_site.notes == "Existing notes"


def test_run_update_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))

    with pytest.raises(MonitoringSiteError, match="MISSING"):
        run_update(UpdateMonitoringSiteInput(id="MISSING", name="Updated"))
