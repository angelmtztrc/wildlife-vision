from pathlib import Path

import platformdirs
import pytest

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.use_cases.monitoring_site import MonitoringSiteInput, MonitoringSiteUpdateInput
from wv.use_cases.monitoring_site import run_create, run_list, run_show, run_update
from wv.use_cases.workspace import WorkspaceInitInput, run_init as run_workspace_init
from wv.workspace.common import WorkspaceError


def test_run_create_requires_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        run_create(MonitoringSiteInput(id="SITE001", name="North Ridge"))


def test_run_create_and_show_return_monitoring_site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    created = run_create(
        MonitoringSiteInput(
            id="SITE001",
            name="North Ridge",
            description="Pine clearing",
            latitude=31.2,
            longitude=-110.9,
            elevation=1250.0,
            notes="Summer",
        )
    )

    shown = run_show("SITE001")

    assert shown == created


def test_run_create_rejects_duplicate_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(MonitoringSiteInput(id="SITE001", name="North Ridge"))

    with pytest.raises(RecordAlreadyExistsError, match="SITE001"):
        run_create(MonitoringSiteInput(id="SITE001", name="Second Name"))


def test_run_list_returns_rows_ordered_by_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(MonitoringSiteInput(id="SITE002", name="Beta"))
    run_create(MonitoringSiteInput(id="SITE001", name="Alpha"))

    result = run_list()

    assert [site.id for site in result] == ["SITE001", "SITE002"]


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
    run_create(MonitoringSiteInput(id="SITE001", name="North Ridge"))

    with pytest.raises(WorkspaceError, match="At least one field"):
        run_update(MonitoringSiteUpdateInput(id="SITE001"))


def test_run_update_applies_partial_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create(
        MonitoringSiteInput(
            id="SITE001",
            name="North Ridge",
            description="Initial",
            notes="Existing notes",
        )
    )

    result = run_update(
        MonitoringSiteUpdateInput(
            id="SITE001",
            name="South Ridge",
            latitude=31.2,
        )
    )

    assert result.id == "SITE001"
    assert result.name == "South Ridge"
    assert result.description == "Initial"
    assert result.latitude == 31.2
    assert result.notes == "Existing notes"


def test_run_update_rejects_missing_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))

    with pytest.raises(RecordNotFoundError, match="MISSING"):
        run_update(MonitoringSiteUpdateInput(id="MISSING", name="Updated"))
