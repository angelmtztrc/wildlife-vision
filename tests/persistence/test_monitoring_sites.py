from pathlib import Path

from wv.models import MonitoringSite
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.database import initialize_database
from wv.persistence.repositories import MonitoringSiteRepository
from wv.persistence.session import session_scope


def test_create_monitoring_site_inserts_row(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with session_scope(database_path) as session:
        repository = MonitoringSiteRepository(session)
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
    with session_scope(database_path) as session:
        assert MonitoringSiteRepository(session).get("SITE001") == record


def test_create_monitoring_site_rejects_duplicate_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    record = MonitoringSite(id="SITE001", name="North Ridge")

    with session_scope(database_path) as session:
        MonitoringSiteRepository(session).create(record)

    with session_scope(database_path) as session:
        try:
            MonitoringSiteRepository(session).create(record)
        except RecordAlreadyExistsError:
            pass
        else:
            raise AssertionError("Expected RecordAlreadyExistsError")


def test_list_monitoring_sites_returns_rows_ordered_by_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with session_scope(database_path) as session:
        repository = MonitoringSiteRepository(session)
        repository.create(MonitoringSite(id="SITE002", name="Beta"))
        repository.create(MonitoringSite(id="SITE001", name="Alpha"))

    with session_scope(database_path) as session:
        result = MonitoringSiteRepository(session).list()

    assert [site.id for site in result] == ["SITE001", "SITE002"]


def test_get_monitoring_site_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with session_scope(database_path) as session:
        try:
            MonitoringSiteRepository(session).get("MISSING")
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")


def test_update_monitoring_site_changes_only_provided_fields(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with session_scope(database_path) as session:
        repository = MonitoringSiteRepository(session)
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

    with session_scope(database_path) as session:
        result = MonitoringSiteRepository(session).update(
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

    with session_scope(database_path) as session:
        try:
            MonitoringSiteRepository(session).update("MISSING", {"name": "Updated"})
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")
