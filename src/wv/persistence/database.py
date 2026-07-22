import sqlite3
from pathlib import Path

from wv.persistence.migrations import apply_migrations


def initialize_database(database_path: Path) -> Path:
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        apply_migrations(connection)

    return database_path
