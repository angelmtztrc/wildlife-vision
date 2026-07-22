from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS = (
    Migration(
        version=1,
        name="create_monitoring_sites_and_devices",
        sql="""
        CREATE TABLE monitoring_sites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            latitude REAL,
            longitude REAL,
            elevation REAL,
            notes TEXT
        );

        CREATE TABLE devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            manufacturer TEXT,
            serial_number TEXT,
            notes TEXT
        );
        """,
    ),
    Migration(
        version=2,
        name="add_device_monitoring_site_and_deployments",
        sql="""
        ALTER TABLE devices ADD COLUMN monitoring_site_id TEXT;

        CREATE TABLE deployments (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            monitoring_site_id TEXT NOT NULL,
            sd_card_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """,
    ),
)


def ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def get_applied_migration_versions(connection: sqlite3.Connection) -> set[int]:
    rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def apply_migrations(connection: sqlite3.Connection) -> None:
    ensure_schema_migrations_table(connection)
    applied_versions = get_applied_migration_versions(connection)

    for migration in MIGRATIONS:
        if migration.version in applied_versions:
            continue

        with connection:
            connection.executescript(migration.sql)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (
                    migration.version,
                    migration.name,
                    datetime.now(UTC).isoformat(),
                ),
            )
