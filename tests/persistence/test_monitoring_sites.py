from pathlib import Path

import pytest

from wv.domain.monitoring_area import MonitoringArea
from wv.domain.monitoring_site import MonitoringSite
from wv.persistence.database import initialize_database
from wv.persistence.repositories import MonitoringAreaRepository, MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope


def test_sites_require_area_and_are_filterable(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        MonitoringAreaRepository(sql_session).create(MonitoringArea("AREA001", "North Ranch"))
        repository = MonitoringSiteRepository(sql_session)
        created = repository.create(MonitoringSite("SITE001", "AREA001", "North Ridge", 31.2, -110.9))
        filtered = repository.list(monitoring_area_id="AREA001")

    assert created.monitoring_area_id == "AREA001"
    assert filtered == [created]


@pytest.mark.parametrize("latitude,longitude", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_site_coordinate_constraints_are_enforced(tmp_path: Path, latitude: float, longitude: float):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        MonitoringAreaRepository(sql_session).create(MonitoringArea("AREA001", "North Ranch"))
        with pytest.raises(Exception, match="ck_sites"):
            MonitoringSiteRepository(sql_session).create(
                MonitoringSite("SITE001", "AREA001", "North Ridge", latitude, longitude)
            )
