from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    read_sd_config,
    resolve_sd_path,
)
from . import _shared as shared
from ._shared import SdError


@dataclass(frozen=True)
class SdShowInput:
    path: Path


@dataclass(frozen=True)
class SdShowResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


def run(input_data: SdShowInput) -> SdShowResult:
    try:
        sd_path = resolve_sd_path(input_data.path)
        config_path = get_sd_config_path(sd_path)
        config = read_sd_config(sd_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc

    return SdShowResult(path=sd_path, config_path=config_path, config=config)
