from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class DeploymentRecord:
    id: str
    device_id: str
    monitoring_site_id: str
    sd_card_path: str
    created_at: str
    updated_at: str


def _row_to_record(row: sqlite3.Row) -> DeploymentRecord:
    return DeploymentRecord(
        id=row["id"],
        device_id=row["device_id"],
        monitoring_site_id=row["monitoring_site_id"],
        sd_card_path=row["sd_card_path"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_deployment(database_path: Path, record: DeploymentRecord) -> DeploymentRecord:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO deployments(
                id,
                device_id,
                monitoring_site_id,
                sd_card_path,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.device_id,
                record.monitoring_site_id,
                record.sd_card_path,
                record.created_at,
                record.updated_at,
            ),
        )

    return record


def list_deployments_for_device(database_path: Path, device_id: str) -> list[DeploymentRecord]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, device_id, monitoring_site_id, sd_card_path, created_at, updated_at
            FROM deployments
            WHERE device_id = ?
            ORDER BY created_at, id
            """,
            (device_id,),
        ).fetchall()

    return [_row_to_record(row) for row in rows]


def list_deployments_for_sd_card(database_path: Path, sd_card_path: str) -> list[DeploymentRecord]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, device_id, monitoring_site_id, sd_card_path, created_at, updated_at
            FROM deployments
            WHERE sd_card_path = ?
            ORDER BY created_at, id
            """,
            (sd_card_path,),
        ).fetchall()

    return [_row_to_record(row) for row in rows]
