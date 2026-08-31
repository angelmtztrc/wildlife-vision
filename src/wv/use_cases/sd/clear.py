from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigError,
    get_sd_config_path,
    remove_sd_config,
    resolve_sd_path,
    sd_operation_lock,
)

from . import _shared as shared


@dataclass(frozen=True)
class SdClearInput:
    path: Path


@dataclass(frozen=True)
class SdClearResult:
    path: Path
    config_path: Path


def run(input_data: SdClearInput) -> SdClearResult:
    try:
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            config_path = get_sd_config_path(sd_path)
            remove_sd_config(config_path)
            return SdClearResult(sd_path, config_path)
    except SdConfigError as exc:
        raise shared.to_sd_error(exc) from exc
