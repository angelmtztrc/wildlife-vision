from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError
from wv.persistence.database import initialize_database
from wv.persistence.devices import DeviceRecord
from wv.persistence.devices import create_device, get_device, list_devices, update_device


def test_create_device_inserts_row(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    record = create_device(
        database_path,
        DeviceRecord(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            serial_number="SN-001",
            notes="Primary unit",
        ),
    )

    assert record.id == "HNT001"
    assert get_device(database_path, "HNT001") == record


def test_create_device_rejects_duplicate_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    record = DeviceRecord(id="HNT001", name="North Camera")
    create_device(database_path, record)

    try:
        create_device(database_path, record)
    except RecordAlreadyExistsError:
        pass
    else:
        raise AssertionError("Expected RecordAlreadyExistsError")


def test_list_devices_returns_rows_ordered_by_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    create_device(database_path, DeviceRecord(id="HNT002", name="Beta"))
    create_device(database_path, DeviceRecord(id="HNT001", name="Alpha"))

    result = list_devices(database_path)

    assert [device.id for device in result] == ["HNT001", "HNT002"]


def test_get_device_rejects_missing_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    try:
        get_device(database_path, "MISSING")
    except RecordNotFoundError:
        pass
    else:
        raise AssertionError("Expected RecordNotFoundError")


def test_update_device_changes_only_provided_fields(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    create_device(
        database_path,
        DeviceRecord(
            id="HNT001",
            name="North Camera",
            manufacturer="Browning",
            serial_number="SN-001",
            notes="Existing notes",
        ),
    )

    result = update_device(
        database_path,
        "HNT001",
        {"name": "South Camera", "notes": "Updated notes"},
    )

    assert result == DeviceRecord(
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

    try:
        update_device(database_path, "MISSING", {"name": "Updated"})
    except RecordNotFoundError:
        pass
    else:
        raise AssertionError("Expected RecordNotFoundError")


def test_update_device_can_set_monitoring_site_id(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)
    create_device(
        database_path,
        DeviceRecord(
            id="HNT001",
            name="North Camera",
        ),
    )

    result = update_device(
        database_path,
        "HNT001",
        {"monitoring_site_id": "SITE001"},
    )

    assert result.monitoring_site_id == "SITE001"
