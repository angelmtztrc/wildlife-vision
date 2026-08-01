from pathlib import Path

import platformdirs
import pytest

from wv.persistence.repositories import DeploymentRepository, DeviceRepository
from wv.persistence.sql_session import sql_session_scope
from wv.use_cases.device.create import CreateDeviceInput, run as _run_create_device
from wv.use_cases.device.show import ShowDeviceInput, run as _run_show_device
from wv.use_cases.monitoring_site.create import (
    CreateMonitoringSiteInput,
    run as run_create_monitoring_site,
)
from wv.use_cases.sd._shared import SdError
from wv.use_cases.sd.clear import SdClearInput, run as run_clear
from wv.use_cases.sd.initialize import SdInitializeInput as SdInitInput
from wv.use_cases.sd.initialize import run as run_init
from wv.use_cases.sd.show import SdShowInput, run as _run_show
from wv.use_cases.sd.sync import SdSyncInput, run as run_sync
from wv.use_cases.sd.update import SdUpdateInput, run as run_update
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_workspace_initialize,
)
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import get_workspace_database_path


def _list_deployments_for_device(database_path: Path, device_id: str):
    with sql_session_scope(database_path) as sql_session:
        return DeploymentRepository(sql_session).list_for_device(device_id)


def _set_device_monitoring_site(
    database_path: Path, device_id: str, monitoring_site_id: str | None
) -> None:
    with sql_session_scope(database_path) as sql_session:
        DeviceRepository(sql_session).update(
            device_id, {"monitoring_site_id": monitoring_site_id}
        )


def run_create_device(input_data: CreateDeviceInput) -> None:
    _run_create_device(input_data)


def run_show_device(device_id: str):
    return _run_show_device(ShowDeviceInput(id=device_id)).device


def run_show(path: Path):
    return _run_show(SdShowInput(path=path))


@pytest.fixture
def configured_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create_device(CreateDeviceInput(id="HNT001", name="North Camera"))
    run_create_device(CreateDeviceInput(id="HNT002", name="South Camera"))
    run_create_monitoring_site(CreateMonitoringSiteInput(id="SITE001", name="North Ridge"))
    run_create_monitoring_site(CreateMonitoringSiteInput(id="SITE002", name="South Ridge"))
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
    monkeypatch.setattr("wv.use_cases.sd.initialize.now_iso", lambda: "2026-07-21T10:00:00+00:00")

    result = run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    assert result.config_path == sd_path / ".wv" / "config.yml"
    assert result.config.device_id == "HNT001"
    assert result.config.monitoring_site_id == "SITE001"
    assert result.config.created_at == "2026-07-21T10:00:00+00:00"
    assert run_show_device("HNT001").monitoring_site_id == "SITE001"

    database_path = get_workspace_database_path(configured_workspace)
    deployments = _list_deployments_for_device(database_path, "HNT001")
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


def test_run_init_rejects_symlinked_sd_root(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    sd_link = tmp_path / "sd-link"
    sd_link.symlink_to(sd_path, target_is_directory=True)

    with pytest.raises(SdError, match="Symbolic links are not supported"):
        run_init(SdInitInput(path=sd_link, device_id="HNT001", monitoring_site_id="SITE001"))

    assert not (sd_path / ".wv").exists()
    assert run_show_device("HNT001").monitoring_site_id is None


def test_run_show_rejects_symlinked_config_file(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    config_path = sd_path / ".wv" / "config.yml"
    config_path.parent.mkdir()
    config_path.symlink_to(tmp_path / "config.yml")

    with pytest.raises(SdError, match="Symbolic links are not supported"):
        run_show(sd_path)


def test_run_update_changes_monitoring_site_and_records_deployment(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    monkeypatch.setattr("wv.use_cases.sd.update.now_iso", lambda: "2026-07-21T11:00:00+00:00")

    result = run_update(SdUpdateInput(path=sd_path, monitoring_site_id="SITE002"))

    assert result.config.device_id == "HNT001"
    assert result.config.monitoring_site_id == "SITE002"
    assert result.config.created_at != result.config.updated_at
    assert run_show_device("HNT001").monitoring_site_id == "SITE002"

    database_path = get_workspace_database_path(configured_workspace)
    deployments = _list_deployments_for_device(database_path, "HNT001")
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

    with pytest.raises(SdError, match="Device not found: UNKNOWN"):
        run_init(SdInitInput(path=sd_path, device_id="UNKNOWN", monitoring_site_id="SITE001"))

    assert not (sd_path / ".wv" / "config.yml").exists()


def test_run_init_removes_config_when_database_update_fails(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    monkeypatch.setattr(
        "wv.use_cases.sd._shared.record_deployment",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("database failure")),
    )

    with pytest.raises(RuntimeError, match="database failure"):
        run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))

    assert not (sd_path / ".wv" / "config.yml").exists()
    assert run_show_device("HNT001").monitoring_site_id is None


def test_run_update_restores_config_when_database_update_fails(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    monkeypatch.setattr(
        "wv.use_cases.sd._shared.record_deployment",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("database failure")),
    )

    with pytest.raises(RuntimeError, match="database failure"):
        run_update(SdUpdateInput(path=sd_path, monitoring_site_id="SITE002"))

    assert run_show(sd_path).config.monitoring_site_id == "SITE001"
    assert run_show_device("HNT001").monitoring_site_id == "SITE001"


def test_run_update_rejects_database_mismatch(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    database_path = get_workspace_database_path(configured_workspace)
    _set_device_monitoring_site(database_path, "HNT001", "SITE002")

    with pytest.raises(SdError, match="wv sd sync"):
        run_update(SdUpdateInput(path=sd_path, monitoring_site_id="SITE002"))

    assert run_show(sd_path).config.monitoring_site_id == "SITE001"


def test_run_update_rejects_identity_noop(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    database_path = get_workspace_database_path(configured_workspace)

    with pytest.raises(SdError, match="already matches"):
        run_update(SdUpdateInput(path=sd_path, monitoring_site_id="SITE001"))

    assert len(_list_deployments_for_device(database_path, "HNT001")) == 1


def test_run_clear_rejects_database_mismatch(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    database_path = get_workspace_database_path(configured_workspace)
    _set_device_monitoring_site(database_path, "HNT001", "SITE002")

    with pytest.raises(SdError, match="wv sd sync"):
        run_clear(SdClearInput(path=sd_path))

    assert (sd_path / ".wv" / "config.yml").exists()


def test_run_clear_restores_assignment_when_config_removal_fails(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    monkeypatch.setattr(
        "wv.use_cases.sd.clear.remove_sd_config",
        lambda path: (_ for _ in ()).throw(OSError("card is read-only")),
    )

    with pytest.raises(SdError, match="database assignment was restored"):
        run_clear(SdClearInput(path=sd_path))

    assert (sd_path / ".wv" / "config.yml").exists()
    assert run_show_device("HNT001").monitoring_site_id == "SITE001"


def test_run_sync_reconciles_database_once(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    run_init(SdInitInput(path=sd_path, device_id="HNT001", monitoring_site_id="SITE001"))
    database_path = get_workspace_database_path(configured_workspace)
    _set_device_monitoring_site(database_path, "HNT001", "SITE002")

    result = run_sync(SdSyncInput(path=sd_path))

    assert result.database_updated is True
    assert result.deployment_recorded is True
    assert run_show_device("HNT001").monitoring_site_id == "SITE001"
    assert len(_list_deployments_for_device(database_path, "HNT001")) == 2

    result = run_sync(SdSyncInput(path=sd_path))

    assert result.database_updated is False
    assert result.deployment_recorded is False
    assert len(_list_deployments_for_device(database_path, "HNT001")) == 2


def test_run_sync_reports_malformed_card_config(
    configured_workspace: Path,
    tmp_path: Path,
):
    sd_path = tmp_path / "sd-card"
    config_path = sd_path / ".wv" / "config.yml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("[")

    with pytest.raises(SdError, match="Could not read SD config"):
        run_sync(SdSyncInput(path=sd_path))
