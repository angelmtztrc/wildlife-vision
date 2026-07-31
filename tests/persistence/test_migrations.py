import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from wv.persistence.alembic import get_alembic_directory
from wv.persistence.database import initialize_database
from wv.persistence.sql_session import build_database_url


def _get_table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    return {row[0] for row in rows}


def _get_migration_version(database_path: Path) -> str:
    with sqlite3.connect(database_path) as connection:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def _get_alembic_config(database_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(get_alembic_directory()))
    config.set_main_option("sqlalchemy.url", build_database_url(database_path))
    return config


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
        "sessions",
        "session_images",
        "session_processes",
    }


def test_initialize_database_records_applied_migration(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    assert _get_migration_version(database_path) == "0003_session_processes"


def test_initialize_database_is_idempotent(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"

    initialize_database(database_path)
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]

    assert count == 1


def test_initialize_database_upgrades_session_inventory_database(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    database_path.parent.mkdir()
    command.upgrade(_get_alembic_config(database_path), "0002_session_inventory")

    initialize_database(database_path)

    assert _get_migration_version(database_path) == "0003_session_processes"
    assert "session_processes" in _get_table_names(database_path)
