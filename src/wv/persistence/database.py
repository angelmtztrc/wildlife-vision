from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from wv.persistence.alembic import get_alembic_directory
from wv.persistence.sql_session import build_database_url


def _build_alembic_config(database_path: Path | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(get_alembic_directory()))
    if database_path is not None:
        config.set_main_option("sqlalchemy.url", build_database_url(database_path))
    return config


def get_database_revision(database_path: Path) -> str | None:
    """Return the Alembic revision recorded by a database.

    Args:
        database_path: SQLite database file to inspect.

    Returns:
        The current Alembic revision, or ``None`` when the database has no
        Alembic version table.

    Raises:
        FileNotFoundError: If ``database_path`` does not exist as a file.
        sqlalchemy.exc.SQLAlchemyError: If the database cannot be inspected.
    """
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    engine = create_engine(build_database_url(database_path))
    try:
        with engine.connect() as connection:
            return MigrationContext.configure(connection).get_current_revision()
    finally:
        engine.dispose()


def get_database_head_revision() -> str:
    """Return the single Alembic head revision packaged with the application.

    Returns:
        The revision identifier at the tip of the packaged migration history.

    Raises:
        alembic.util.CommandError: If the migration history has multiple heads.
    """
    return ScriptDirectory.from_config(_build_alembic_config()).get_current_head()


def upgrade_database(database_path: Path) -> None:
    """Apply all pending packaged Alembic migrations to a database.

    Args:
        database_path: SQLite database file to upgrade.

    Raises:
        alembic.util.CommandError: If Alembic cannot apply the migration plan.
        sqlalchemy.exc.SQLAlchemyError: If the database cannot be migrated.
    """
    command.upgrade(_build_alembic_config(database_path), "head")


def initialize_database(database_path: Path) -> Path:
    """Create a database parent directory and upgrade its schema to Alembic head.

    Args:
        database_path: SQLite database file to initialize or upgrade.

    Returns:
        The initialized database path.

    Raises:
        alembic.util.CommandError: If Alembic cannot apply the migration plan.
        sqlalchemy.exc.SQLAlchemyError: If the database cannot be initialized.

    Side Effects:
        Creates parent directories when absent and applies pending migrations.
    """
    database_path.parent.mkdir(parents=True, exist_ok=True)
    upgrade_database(database_path)

    return database_path
