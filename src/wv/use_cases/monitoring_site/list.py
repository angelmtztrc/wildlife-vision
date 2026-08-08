from dataclasses import dataclass, field

from wv.domain.monitoring_site import MonitoringSite
from wv.persistence.common import PersistenceError
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope
from wv.workspace.workspace_config import require_workspace_database_path

from . import _shared as shared


@dataclass(frozen=True)
class ListMonitoringSitesInput:
    monitoring_area_id: str | None = None


@dataclass(frozen=True)
class ListMonitoringSitesResult:
    items: list[MonitoringSite] = field(default_factory=list)


def run(input_data: ListMonitoringSitesInput) -> ListMonitoringSitesResult:
    try:
        with sql_session_scope(require_workspace_database_path()) as sql_session:
            monitoring_sites = MonitoringSiteRepository(sql_session).list(
                monitoring_area_id=input_data.monitoring_area_id
            )
    except PersistenceError as exc:
        raise shared.to_monitoring_site_error(exc) from exc

    return ListMonitoringSitesResult(items=monitoring_sites)
