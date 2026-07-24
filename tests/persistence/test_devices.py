from pathlib import Path

from wv.models import Device
from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.database import initialize_database
from wv.persistence.repositories import DeviceRepository
from wv.persistence.sql_session import sql_session_scope


def test_create_device_inserts_row(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        repository = DeviceRepository(sql_session)
        record = repository.create(
            Device(
                id="HNT001",
                name="North Camera",
                manufacturer="Browning",
                serial_number="SN-001",
                notes="Primary unit",
            )
        )

    assert record.id == "HNT001"
    with sql_session_scope(database_path) as sql_session:
        assert DeviceRepository(sql_session).get("HNT001") == record


def test_create_device_rejects_duplicate_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    record = Device(id="HNT001", name="North Camera")

    with sql_session_scope(database_path) as sql_session:
        DeviceRepository(sql_session).create(record)

    with sql_session_scope(database_path) as sql_session:
        try:
            DeviceRepository(sql_session).create(record)
        except RecordAlreadyExistsError:
            pass
        else:
            raise AssertionError("Expected RecordAlreadyExistsError")


def test_list_devices_returns_rows_ordered_by_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        repository = DeviceRepository(sql_session)
        repository.create(Device(id="HNT002", name="Beta"))
        repository.create(Device(id="HNT001", name="Alpha"))

    with sql_session_scope(database_path) as sql_session:
        result = DeviceRepository(sql_session).list()

    assert [device.id for device in result] == ["HNT001", "HNT002"]


def test_get_device_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        try:
            DeviceRepository(sql_session).get("MISSING")
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")


def test_update_device_changes_only_provided_fields(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        repository = DeviceRepository(sql_session)
        repository.create(
            Device(
                id="HNT001",
                name="North Camera",
                manufacturer="Browning",
                serial_number="SN-001",
                notes="Existing notes",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        result = DeviceRepository(sql_session).update(
            "HNT001",
            {"name": "South Camera", "notes": "Updated notes"},
        )

    assert result == Device(
        id="HNT001",
        name="South Camera",
        manufacturer="Browning",
        serial_number="SN-001",
        notes="Updated notes",
        monitoring_site_id=None,
    )


def test_update_device_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sql_session_scope(database_path) as sql_session:
        try:
            DeviceRepository(sql_session).update("MISSING", {"name": "Updated"})
        except RecordNotFoundError:
            pass
        else:
            raise AssertionError("Expected RecordNotFoundError")


def test_update_device_can_set_monitoring_site_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    with sql_session_scope(database_path) as sql_session:
        repository = DeviceRepository(sql_session)
        repository.create(
            Device(
                id="HNT001",
                name="North Camera",
            )
        )

    with sql_session_scope(database_path) as sql_session:
        result = DeviceRepository(sql_session).update(
            "HNT001",
            {"monitoring_site_id": "SITE001"},
        )

    assert result.monitoring_site_id == "SITE001"
