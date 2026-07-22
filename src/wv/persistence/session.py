from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_database_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve()}"


@lru_cache(maxsize=None)
def _get_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def get_engine(database_path: Path) -> Engine:
    return _get_engine(build_database_url(database_path))


def get_session_factory(database_path: Path) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_path), expire_on_commit=False)


@contextmanager
def session_scope(database_path: Path) -> Iterator[Session]:
    session = get_session_factory(database_path)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
