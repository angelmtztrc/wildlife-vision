from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.database import initialize_database
from wv.persistence.monitoring_sites import MonitoringSiteRecord
from wv.persistence.monitoring_sites import (
    create_monitoring_site,
    get_monitoring_site,
    list_monitoring_sites,
    update_monitoring_site,
)


def test_create_monitoring_site_inserts_row(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    record = create_monitoring_site(
        database_path,
        MonitoringSiteRecord(
            id="SITE001",
            name="North Ridge",
            description="Pine clearing",
            latitude=31.2,
            longitude=-110.9,
            elevation=1250.0,
            notes="Active in summer",
        ),
    )

    assert record.id == "SITE001"
    assert get_monitoring_site(database_path, "SITE001") == record


def test_create_monitoring_site_rejects_duplicate_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    record = MonitoringSiteRecord(id="SITE001", name="North Ridge")
    create_monitoring_site(database_path, record)

    try:
        create_monitoring_site(database_path, record)
    except RecordAlreadyExistsError:
        pass
    else:
        raise AssertionError("Expected RecordAlreadyExistsError")


def test_list_monitoring_sites_returns_rows_ordered_by_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    create_monitoring_site(database_path, MonitoringSiteRecord(id="SITE002", name="Beta"))
    create_monitoring_site(database_path, MonitoringSiteRecord(id="SITE001", name="Alpha"))

    result = list_monitoring_sites(database_path)

    assert [site.id for site in result] == ["SITE001", "SITE002"]


def test_get_monitoring_site_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    try:
        get_monitoring_site(database_path, "MISSING")
    except RecordNotFoundError:
        pass
    else:
        raise AssertionError("Expected RecordNotFoundError")


def test_update_monitoring_site_changes_only_provided_fields(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    create_monitoring_site(
        database_path,
        MonitoringSiteRecord(
            id="SITE001",
            name="North Ridge",
            description="Initial",
            latitude=31.2,
            longitude=-110.9,
            elevation=1250.0,
            notes="Existing notes",
        ),
    )

    result = update_monitoring_site(
        database_path,
        "SITE001",
        {"name": "South Ridge", "notes": "Updated notes"},
    )

    assert result == MonitoringSiteRecord(
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

    try:
        update_monitoring_site(database_path, "MISSING", {"name": "Updated"})
    except RecordNotFoundError:
        pass
    else:
        raise AssertionError("Expected RecordNotFoundError")
