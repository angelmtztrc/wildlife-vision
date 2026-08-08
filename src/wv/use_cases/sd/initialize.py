from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigDurabilityError,
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    now_iso,
    resolve_sd_path,
    sd_operation_lock,
    write_sd_config,
)
from wv.persistence.common import RecordNotFoundError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class SdInitializeInput:
    path: Path
    monitoring_site_id: str


@dataclass(frozen=True)
class SdInitializeResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


def run(input_data: SdInitializeInput) -> SdInitializeResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            config_path = get_sd_config_path(sd_path)
            if config_path.exists():
                raise shared.SdError(f"SD config already exists at {config_path}. Use 'wv sd update' instead.")
            with sql_session_scope(database_path) as sql_session:
                MonitoringSiteRepository(sql_session).get(input_data.monitoring_site_id)
            timestamp = now_iso()
            config = SdConfigRecord(input_data.monitoring_site_id, timestamp, timestamp)
            write_sd_config(config_path, config)
            return SdInitializeResult(sd_path, config_path, config)
    except (SdConfigError, RecordNotFoundError) as exc:
        raise shared.to_sd_error(exc) from exc
