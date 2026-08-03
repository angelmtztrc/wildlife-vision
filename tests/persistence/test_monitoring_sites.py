from pathlib import Path

from wv.domain.monitoring_site import MonitoringSite
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.database import initialize_database
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.sql_session import sql_session_scope


def test_create_monitoring_site_inserts_row(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        repository = MonitoringSiteRepository(sql_session)
        record = repository.create(
            MonitoringSite(
                id="SITE001",
                name="North Ridge",
                description="Pine clearing",
                latitude=31.2,
                longitude=-110.9,
                elevation=1250.0,
                notes="Active in summer",
            )
        )

    assert record.id == "SITE001"
    with sql_session_scope(database_path) as sql_session:
        assert MonitoringSiteRepository(sql_session).get("SITE001") == record


def test_create_monitoring_site_rejects_duplicate_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    record = MonitoringSite(id="SITE001", name="North Ridge")

    with sql_session_scope(database_path) as sql_session:
        MonitoringSiteRepository(sql_session).create(record)

    with sql_session_scope(database_path) as sql_session:
        try:
            MonitoringSiteRepository(sql_session).create(record)
        except RecordAlreadyExistsError:
            pass
        else:
            raise AssertionError("Expected RecordAlreadyExistsError")


def test_list_monitoring_sites_returns_rows_ordered_by_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        repository = MonitoringSiteRepository(sql_session)
        repository.create(MonitoringSite(id="SITE002", name="Beta"))
        repository.create(MonitoringSite(id="SITE001", name="Alpha"))

    with sql_session_scope(database_path) as sql_session:
        result = MonitoringSiteRepository(sql_session).list()

    assert [site.id for site in result] == ["SITE001", "SITE002"]


def test_get_monitoring_site_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        try:
            MonitoringSiteRepository(sql_session).get("MISSING")
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")


def test_update_monitoring_site_changes_only_provided_fields(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        repository = MonitoringSiteRepository(sql_session)
        repository.create(
            MonitoringSite(
                id="SITE001",
                name="North Ridge",
                description="Initial",
                latitude=31.2,
                longitude=-110.9,
                elevation=1250.0,
                notes="Existing notes",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        result = MonitoringSiteRepository(sql_session).update(
            "SITE001",
            {"name": "South Ridge", "notes": "Updated notes"},
        )

    assert result == MonitoringSite(
        id="SITE001",
        name="South Ridge",
        description="Initial",
        latitude=31.2,
        longitude=-110.9,
        elevation=1250.0,
        notes="Updated notes",
    )


def test_update_monitoring_site_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        try:
            MonitoringSiteRepository(sql_session).update("MISSING", {"name": "Updated"})
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")
