from pathlib import Path


def get_alembic_directory() -> Path:
    return Path(__file__).resolve().parent
