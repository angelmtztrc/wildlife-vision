import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import piexif
import pytest
from PIL import Image
from typer.testing import CliRunner

import wv.config as config
from wv.cli.runtime import reset_runtime


@pytest.fixture(autouse=True)
def clear_config_caches():
    reset_runtime()
    config.load.cache_clear()
    config.get_repo_root.cache_clear()
    yield
    reset_runtime()
    config.load.cache_clear()
    config.get_repo_root.cache_clear()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


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
