from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session as SqlSession
from sqlalchemy.orm import sessionmaker


def build_database_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve()}"


@lru_cache(maxsize=None)
def _get_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    return engine


def get_engine(database_path: Path) -> Engine:
    return _get_engine(build_database_url(database_path))


def get_sql_session_factory(database_path: Path) -> sessionmaker[SqlSession]:
    return sessionmaker(bind=get_engine(database_path), expire_on_commit=False)


@contextmanager
def sql_session_scope(database_path: Path) -> Iterator[SqlSession]:
    sql_session = get_sql_session_factory(database_path)()
    try:
        yield sql_session
        sql_session.commit()
    except Exception:
        sql_session.rollback()
        raise
    finally:
        sql_session.close()
