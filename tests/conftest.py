import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import piexif
import platformdirs
import pytest
from PIL import Image
from typer.testing import CliRunner

import wv.config as config
from wv.core.logger import reset_logging
from wv.use_cases.device.create import CreateDeviceInput, run as run_create_device
from wv.use_cases.monitoring_site.create import (
    CreateMonitoringSiteInput,
    run as run_create_monitoring_site,
)
from wv.use_cases.monitoring_area.create import (
    CreateMonitoringAreaInput,
    run as run_create_monitoring_area,
)
from wv.use_cases.workspace.initialize import (
    WorkspaceInitializeInput,
    run as run_workspace_initialize,
)


@pytest.fixture(autouse=True)
def clear_config_caches():
    reset_logging()
    config.load.cache_clear()
    config.get_repo_root.cache_clear()
    yield
    reset_logging()
    config.load.cache_clear()
    config.get_repo_root.cache_clear()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def configured_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_workspace_initialize(WorkspaceInitializeInput(path=workspace_path))
    run_create_device(CreateDeviceInput(id="HNT001", name="North Camera"))
    run_create_monitoring_area(CreateMonitoringAreaInput(id="AREA001", name="North Ranch"))
    run_create_monitoring_site(
        CreateMonitoringSiteInput(
            id="SITE001",
            monitoring_area_id="AREA001",
            name="North Ridge",
            latitude=28.55,
            longitude=-101.14,
        )
    )
    run_create_monitoring_site(
        CreateMonitoringSiteInput(
            id="SITE002",
            monitoring_area_id="AREA001",
            name="South Ridge",
            latitude=28.56,
            longitude=-101.15,
        )
    )
    return workspace_path


@pytest.fixture
def make_image() -> Callable[..., Path]:
    def _make_image(
        path: Path,
        color: tuple[int, int, int] = (128, 128, 128),
        size: tuple[int, int] = (16, 16),
        exif: dict[str, str] | None = None,
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", size=size, color=color)
        exif_dict: dict[str, dict[int, str | bytes] | None] = {
            "0th": {},
            "Exif": {},
            "GPS": {},
            "1st": {},
            "thumbnail": None,
        }

        if exif:
            for key, value in exif.items():
                if key == "DateTime":
                    exif_dict["0th"][piexif.ImageIFD.DateTime] = value
                elif key == "DateTimeOriginal":
                    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = value
                elif key == "ImageDescription":
                    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = value.encode(
                        "utf-8"
                    )
                else:
                    raise ValueError(f"Unsupported EXIF key: {key}")

        save_kwargs = {}
        if exif_dict["0th"] or exif_dict["Exif"]:
            save_kwargs["exif"] = piexif.dump(exif_dict)

        image.save(path, **save_kwargs)
        return path

    return _make_image


@pytest.fixture
def make_corrupted_image() -> Callable[[Path], Path]:
    def _make_corrupted_image(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not a valid image file")
        return path

    return _make_corrupted_image


@pytest.fixture
def set_mtime() -> Callable[[Path, datetime], Path]:
    def _set_mtime(path: Path, value: datetime) -> Path:
        timestamp = value.timestamp()
        os.utime(path, (timestamp, timestamp))
        return path

    return _set_mtime
