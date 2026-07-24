from datetime import datetime
from pathlib import Path

import pytest
import platformdirs

import wv.use_cases.ingest.common as common
import wv.use_cases.ingest.sd as sd
from wv.persistence.common import RecordNotFoundError
from wv.use_cases.sd import SdError
from wv.workspace.common import WorkspaceError


class FrozenDateTime:
    @classmethod
    def now(cls) -> datetime:
        return datetime(2024, 6, 28, 12, 0, 0)


def _freeze_ingest_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        common,
        "get_image_datetime",
        lambda file_path: datetime(2024, 6, 28, 10, 15, 30),
    )


def _write_sd_config(source: Path, device_id: str = "HNT001", site_id: str = "SITE001") -> None:
    config_path = source / ".wv" / "config.yml"
    config_path.parent.mkdir()
    config_path.write_text(
        "\n".join(
            [
                f"device_id: {device_id}",
                f"monitoring_site_id: {site_id}",
                "created_at: '2026-07-21T10:00:00+00:00'",
                "updated_at: '2026-07-21T10:00:00+00:00'",
            ]
        )
    )


def test_run_dry_copy_uses_sd_config_and_workspace_session(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    (source / "notes.txt").write_text("ignore me")
    (source / "subdir").mkdir()
    _write_sd_config(source)
    _freeze_ingest_environment(monkeypatch)

    result = sd.run(sd.IngestSdInput(source=source, mode="copy", dry_run=True))

    assert result.destination == (
        configured_workspace / "sessions" / "20240628_120000__HNT001" / "init"
    )
    assert result.files_discovered == 3
    assert result.files_copied == 1
    assert result.files_deleted == 0
    assert result.files_ignored == 2
    assert result.files_failed == 0
    assert result.dry_run is True
    assert image_path.exists()
    assert not result.destination.exists()


def test_run_drain_writes_expected_file_and_deletes_source(
    configured_workspace: Path,
    make_image,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    source.mkdir()
    image_path = make_image(source / "capture.jpg")
    _write_sd_config(source)
    _freeze_ingest_environment(monkeypatch)

    file_id = common.get_file_id(image_path)
    result = sd.run(sd.IngestSdInput(source=source, mode="drain"))
    expected_destination = (
        configured_workspace
        / "sessions"
        / "20240628_120000__HNT001"
        / "init"
        / f"20240628_101530__SITE001__{file_id}.jpg"
    )
    assert result.files_copied == 1
    assert result.files_deleted == 1
    assert result.files_failed == 0
    assert expected_destination.exists()
    assert not image_path.exists()


def test_run_rejects_missing_sd_config(configured_workspace: Path, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(SdError, match="SD config file not found"):
        sd.run(sd.IngestSdInput(source=source, mode="copy"))


def test_run_rejects_unregistered_sd_config_identity(
    configured_workspace: Path, tmp_path: Path
):
    source = tmp_path / "source"
    source.mkdir()
    _write_sd_config(source, device_id="UNKNOWN")

    with pytest.raises(RecordNotFoundError, match="Device not found: UNKNOWN"):
        sd.run(sd.IngestSdInput(source=source, mode="copy"))


def test_run_requires_configured_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    source.mkdir()
    _write_sd_config(source)
    monkeypatch.setattr(
        platformdirs, "user_config_path", lambda *args, **kwargs: tmp_path / "user-config"
    )

    with pytest.raises(WorkspaceError, match="No workspace configured"):
        sd.run(sd.IngestSdInput(source=source, mode="copy"))
