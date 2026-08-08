import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.util import CommandError
import pytest

from wv.persistence.alembic import get_alembic_directory
from wv.persistence.database import (
    get_database_head_revision,
    get_database_revision,
    initialize_database,
    upgrade_database,
)
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
        "monitoring_areas",
        "monitoring_sites",
        "devices",
        "sessions",
        "session_images",
        "session_processes",
        "session_process_image_plans",
    }


def test_initialize_database_records_applied_migration(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    initialize_database(database_path)

    assert _get_migration_version(database_path) == get_database_head_revision()


def test_initialize_database_is_idempotent(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"

    initialize_database(database_path)
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM alembic_version").fetchone()[0]

    assert count == 1


def test_upgrade_database_upgrades_session_process_database(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    database_path.parent.mkdir()
    command.upgrade(_get_alembic_config(database_path), "0003_session_processes")

    upgrade_database(database_path)

    assert _get_migration_version(database_path) == get_database_head_revision()
    assert "session_process_image_plans" in _get_table_names(database_path)


def test_upgrade_database_refuses_populated_clean_break_workspace(tmp_path: Path):
    database_path = tmp_path / ".wv" / "database.sqlite"
    database_path.parent.mkdir()
    command.upgrade(_get_alembic_config(database_path), "0006_session_detection_plan_details")
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO devices (id, name) VALUES ('HNT001', 'North Camera')")

    with pytest.raises(CommandError, match="destructive clean-break"):
        upgrade_database(database_path)


def test_get_database_revision_returns_none_for_unversioned_database(tmp_path: Path):
    database_path = tmp_path / "database.sqlite"
    database_path.touch()

    assert get_database_revision(database_path) is None
