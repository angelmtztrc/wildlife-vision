import sqlite3
from pathlib import Path

from wv.persistence.database import initialize_database


def _get_table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    return {row[0] for row in rows}


def test_initialize_database_applies_initial_schema(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"

    result = initialize_database(database_path)

    assert result == database_path
    assert database_path.is_file()
    assert _get_table_names(database_path) >= {
        "alembic_version",
        "monitoring_sites",
        "devices",
        "deployments",
    }


def test_initialize_database_records_applied_migration(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert version == ("0001_initial_schema",)


def test_initialize_database_is_idempotent(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"

    initialize_database(database_path)
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]

    assert count == 1
