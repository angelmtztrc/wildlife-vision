import sqlite3
from dataclasses import dataclass
from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError


@dataclass(frozen=True)
class DeviceRecord:
    id: str
    name: str
    manufacturer: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    monitoring_site_id: str | None = None


def _row_to_record(row: sqlite3.Row) -> DeviceRecord:
    return DeviceRecord(
        id=row["id"],
        name=row["name"],
        manufacturer=row["manufacturer"],
        serial_number=row["serial_number"],
        notes=row["notes"],
        monitoring_site_id=row["monitoring_site_id"],
    )


def create_device(database_path: Path, record: DeviceRecord) -> DeviceRecord:
    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO devices(id, name, manufacturer, serial_number, notes, monitoring_site_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.name,
                    record.manufacturer,
                    record.serial_number,
                    record.notes,
                    record.monitoring_site_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise RecordAlreadyExistsError(f"Device already exists: {record.id}") from exc

    return record


def list_devices(database_path: Path) -> list[DeviceRecord]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, name, manufacturer, serial_number, notes, monitoring_site_id
            FROM devices
            ORDER BY id
            """
        ).fetchall()

    return [_row_to_record(row) for row in rows]


def get_device(database_path: Path, device_id: str) -> DeviceRecord:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, name, manufacturer, serial_number, notes, monitoring_site_id
            FROM devices
            WHERE id = ?
            """,
            (device_id,),
        ).fetchone()

    if row is None:
        raise RecordNotFoundError(f"Device not found: {device_id}")

    return _row_to_record(row)


def update_device(
    database_path: Path, device_id: str, updates: dict[str, str | None]
) -> DeviceRecord:
    assignments = ", ".join(f"{column} = ?" for column in updates)
    parameters = [*updates.values(), device_id]

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            f"UPDATE devices SET {assignments} WHERE id = ?",
            parameters,
        )

        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Device not found: {device_id}")

    return get_device(database_path, device_id)
