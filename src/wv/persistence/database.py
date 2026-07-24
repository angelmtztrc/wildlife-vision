from pathlib import Path

from alembic import command
from alembic.config import Config

from wv.persistence.alembic import get_alembic_directory
from wv.persistence.sql_session import build_database_url


def initialize_database(database_path: Path) -> Path:
    database_path.parent.mkdir(parents=True, exist_ok=True)

    config = Config()
    config.set_main_option("script_location", str(get_alembic_directory()))
    config.set_main_option("sqlalchemy.url", build_database_url(database_path))
    command.upgrade(config, "head")

    return database_path
