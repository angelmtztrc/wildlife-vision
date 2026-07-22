from pathlib import Path

import platformdirs
import pytest

from wv.persistence.deployments import list_deployments_for_device
from wv.use_cases.device import DeviceInput, run_create as run_create_device, run_show as run_show_device
from wv.use_cases.monitoring_site import MonitoringSiteInput, run_create as run_create_monitoring_site
from wv.use_cases.sd import (
    RecordNotFoundError,
    SdClearInput,
    SdError,
    SdInitInput,
    SdUpdateInput,
    run_clear,
    run_init,
    run_show,
    run_update,
)
from wv.use_cases.workspace import WorkspaceInitInput, run_init as run_workspace_init
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import get_workspace_database_path


@pytest.fixture
def configured_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_init(WorkspaceInitInput(path=workspace_path))
    run_create_device(DeviceInput(id="HNT001", name="North Camera"))
    run_create_device(DeviceInput(id="HNT002", name="South Camera"))
    run_create_monitoring_site(MonitoringSiteInput(id="SITE001", name="North Ridge"))
    run_create_monitoring_site(MonitoringSiteInput(id="SITE002", name="South Ridge"))
    return workspace_path


def test_run_init_requires_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "user-config"
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))


def test_run_init_writes_config_updates_device_and_records_deployment(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    monkeypatch.setattr("wv.use_cases.sd._now_iso", lambda: "2026-07-21T10:00:00+00:00")

    result = run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    assert result.config_path == sd_path / ".wv" / "config.yml"
    assert result.config.device_id == "HNT001"
    assert result.config.monitoring_site_id == "SITE001"
    assert result.config.created_at == "2026-07-21T10:00:00+00:00"
    assert run_show_device("HNT001").monitoring_site_id == "SITE001"

    database_path = get_workspace_database_path(configured_workspace)
    deployments = list_deployments_for_device(database_path, "HNT001")
    assert len(deployments) == 1
    assert deployments[0].sd_card_path == str(sd_path.resolve())


def test_run_init_rejects_existing_config(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    with pytest.raises(SdError, match="wv sd update"):
        run_init(SdInitInput(path=sd_path, device_id="HNT002", monitoring_site_id="SITE002"))


def test_run_init_rejects_device_already_assigned(
    configured_workspace: Path,
    tmp_path: Path,
):
    first_sd_path = tmp_path / "sd-card-1"
    second_sd_path = tmp_path / "sd-card-2"
    first_sd_path.mkdir()
    second_sd_path.mkdir()
    run_init(SdInitInput(path=first_sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    with pytest.raises(SdError, match="already assigned"):
        run_init(SdInitInput(path=second_sd_path, device_id="HNT001", monitoring_site_id="SITE002"))


def test_run_show_reads_existing_config(configured_workspace: Path, tmp_path: Path):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    result = run_show(sd_path)

    assert result.config.device_id == "HNT001"
    assert result.config.monitoring_site_id == "SITE001"


def test_run_show_rejects_missing_config(tmp_path: Path):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()

    with pytest.raises(SdError, match="not found"):
        run_show(sd_path)


def test_run_update_changes_monitoring_site_and_records_deployment(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    monkeypatch.setattr("wv.use_cases.sd._now_iso", lambda: "2026-07-21T11:00:00+00:00")

    result = run_update(SdUpdateInput(path=sd_path, monitoring_site_id="SITE002"))

    assert result.config.device_id == "HNT001"
    assert result.config.monitoring_site_id == "SITE002"
    assert result.config.created_at != result.config.updated_at
    assert run_show_device("HNT001").monitoring_site_id == "SITE002"

    database_path = get_workspace_database_path(configured_workspace)
    deployments = list_deployments_for_device(database_path, "HNT001")
    assert len(deployments) == 2


def test_run_update_can_switch_devices(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    result = run_update(
        SdUpdateInput(path=sd_path, device_id="HNT002", monitoring_site_id="SITE002")
    )

    assert result.config.device_id == "HNT002"
    assert run_show_device("HNT001").monitoring_site_id is None
    assert run_show_device("HNT002").monitoring_site_id == "SITE002"


def test_run_update_rejects_new_device_when_already_assigned(
    configured_workspace: Path,
    tmp_path: Path,
):
    first_sd_path = tmp_path / "sd-card-1"
    second_sd_path = tmp_path / "sd-card-2"
    first_sd_path.mkdir()
    second_sd_path.mkdir()
    run_init(SdInitInput(path=first_sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    run_init(SdInitInput(path=second_sd_path, device_id="HNT002", monitoring_site_id="SITE002"))

    with pytest.raises(SdError, match="already assigned"):
        run_update(SdUpdateInput(path=first_sd_path, device_id="HNT002"))


def test_run_update_requires_at_least_one_field(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    with pytest.raises(SdError, match="At least one field"):
        run_update(SdUpdateInput(path=sd_path))


def test_run_clear_removes_config_and_clears_device_assignment(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    result = run_clear(SdClearInput(path=sd_path))

    assert result.cleared_device_id == "HNT001"
    assert not result.config_path.exists()
    assert run_show_device("HNT001").monitoring_site_id is None


def test_run_init_rejects_unknown_records(configured_workspace: Path, tmp_path: Path):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()

    with pytest.raises(RecordNotFoundError):
        run_init(SdInitInput(path=sd_path, device_id="UNKNOWN", monitoring_site_id="SITE001"))
