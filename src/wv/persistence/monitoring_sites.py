import sqlite3
from dataclasses import dataclass
from pathlib import Path

from wv.persistence.common import RecordAlreadyExistsError, RecordNotFoundError


@dataclass(frozen=True)
class MonitoringSiteRecord:
    id: str
    name: str
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None
    notes: str | None = None


def _row_to_record(row: sqlite3.Row) -> MonitoringSiteRecord:
    return MonitoringSiteRecord(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        elevation=row["elevation"],
        notes=row["notes"],
    )


def create_monitoring_site(database_path: Path, record: MonitoringSiteRecord) -> MonitoringSiteRecord:
    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO monitoring_sites(
                    id,
                    name,
                    description,
                    latitude,
                    longitude,
                    elevation,
                    notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.name,
                    record.description,
                    record.latitude,
                    record.longitude,
                    record.elevation,
                    record.notes,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise RecordAlreadyExistsError(
                f"Monitoring site already exists: {record.id}"
            ) from exc

    return record


def list_monitoring_sites(database_path: Path) -> list[MonitoringSiteRecord]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, name, description, latitude, longitude, elevation, notes
            FROM monitoring_sites
            ORDER BY id
            """
        ).fetchall()

    return [_row_to_record(row) for row in rows]


def get_monitoring_site(database_path: Path, site_id: str) -> MonitoringSiteRecord:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, name, description, latitude, longitude, elevation, notes
            FROM monitoring_sites
            WHERE id = ?
            """,
            (site_id,),
        ).fetchone()

    if row is None:
        raise RecordNotFoundError(f"Monitoring site not found: {site_id}")

    return _row_to_record(row)


def update_monitoring_site(
    database_path: Path, site_id: str, updates: dict[str, str | float | None]
) -> MonitoringSiteRecord:
    assignments = ", ".join(f"{column} = ?" for column in updates)
    parameters = [*updates.values(), site_id]

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            f"UPDATE monitoring_sites SET {assignments} WHERE id = ?",
            parameters,
        )

        if cursor.rowcount == 0:
            raise RecordNotFoundError(f"Monitoring site not found: {site_id}")

    return get_monitoring_site(database_path, site_id)
