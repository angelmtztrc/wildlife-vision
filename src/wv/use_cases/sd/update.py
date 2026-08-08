from dataclasses import dataclass
from pathlib import Path

from wv.core.sd_config import (
    SdConfigError,
    SdConfigRecord,
    get_sd_config_path,
    load_sd_config,
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
class SdUpdateInput:
    path: Path
    monitoring_site_id: str


@dataclass(frozen=True)
class SdUpdateResult:
    path: Path
    config_path: Path
    config: SdConfigRecord


def run(input_data: SdUpdateInput) -> SdUpdateResult:
    try:
        database_path = require_workspace_database_path()
        sd_path = resolve_sd_path(input_data.path)
        with sd_operation_lock(sd_path):
            config_path = get_sd_config_path(sd_path)
            current = load_sd_config(config_path)
            if current.monitoring_site_id == input_data.monitoring_site_id:
                raise shared.SdError("SD config already matches the requested monitoring site.")
            with sql_session_scope(database_path) as sql_session:
                MonitoringSiteRepository(sql_session).get(input_data.monitoring_site_id)
            config = SdConfigRecord(
                input_data.monitoring_site_id, current.created_at, now_iso()
            )
            write_sd_config(config_path, config)
            return SdUpdateResult(sd_path, config_path, config)
    except (SdConfigError, RecordNotFoundError) as exc:
        raise shared.to_sd_error(exc) from exc
