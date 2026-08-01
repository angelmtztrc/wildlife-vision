import stat
import sqlite3
from pathlib import Path

import platformdirs
import pytest
from alembic import command
from alembic.config import Config

from wv.persistence.alembic import get_alembic_directory
from wv.persistence.database import get_database_head_revision
from wv.persistence.sql_session import build_database_url
from wv.use_cases.workspace.initialize import WorkspaceInitializeInput, run as run_initialize
from wv.use_cases.workspace.migrate import WorkspaceMigrateInput, run as run_migrate
from wv.use_cases.workspace.show import WorkspaceShowInput, run as run_show
from wv.use_cases.workspace.validate import WorkspaceValidateInput, run as run_validate
from wv.workspace.common import WorkspaceError


def _get_table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    return {row[0] for row in rows}


def _downgrade_database(database_path: Path) -> None:
    config = Config()
    config.set_main_option("script_location", str(get_alembic_directory()))
    config.set_main_option("sqlalchemy.url", build_database_url(database_path))
    command.downgrade(config, "0003_session_processes")


def test_run_init_creates_workspace_structure(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    result = run_initialize(WorkspaceInitializeInput(path=workspace_path))

    assert result.workspace_path == workspace_path.resolve()
    assert (workspace_path / "sessions").is_dir()
    assert (workspace_path / "models").is_dir()
    assert (workspace_path / "exports").is_dir()
    assert (workspace_path / ".wv").is_dir()
    assert (workspace_path / ".wv" / "database.sqlite").is_file()
    assert (workspace_path / ".wv" / "config.yml").is_file()
    assert _get_table_names(workspace_path / ".wv" / "database.sqlite") >= {
        "alembic_version",
        "monitoring_sites",
        "devices",
        "deployments",
    }
    assert result.global_config_file == config_dir / "config.yml"
    assert "workspace:" in result.global_config_file.read_text()


def test_run_init_rejects_missing_path(tmp_path: Path):
    with pytest.raises(WorkspaceError, match="does not exist"):
        run_initialize(WorkspaceInitializeInput(path=tmp_path / "missing"))


def test_run_init_rejects_non_directory(tmp_path: Path):
    file_path = tmp_path / "workspace.txt"
    file_path.write_text("not a directory")

    with pytest.raises(WorkspaceError, match="not a directory"):
        run_initialize(WorkspaceInitializeInput(path=file_path))


def test_run_init_rejects_unwritable_path(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    workspace_path.chmod(stat.S_IRUSR | stat.S_IXUSR)

    try:
        with pytest.raises(WorkspaceError, match="not writable"):
            run_initialize(WorkspaceInitializeInput(path=workspace_path))
    finally:
        workspace_path.chmod(stat.S_IRWXU)


def test_run_init_rejects_existing_workspace(tmp_path: Path):
    workspace_path = tmp_path / "workspace"
    (workspace_path / ".wv").mkdir(parents=True)

    with pytest.raises(WorkspaceError, match="already exists"):
        run_initialize(WorkspaceInitializeInput(path=workspace_path))


def test_get_status_returns_not_configured_when_global_config_missing(
    tmp_path: Path, monkeypatch
):
    config_dir = tmp_path / "user-config"
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)

    status = run_show(WorkspaceShowInput()).status

    assert status.workspace_path is None
    assert status.exists is False
    assert status.database_exists is False


def test_validate_accepts_complete_workspace(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))

    status = run_validate(WorkspaceValidateInput()).status

    assert status.workspace_path == workspace_path.resolve()
    assert status.database_exists is True


def test_validate_rejects_missing_workspace_parts(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    (workspace_path / "models").rmdir()

    with pytest.raises(WorkspaceError, match="models"):
        run_validate(WorkspaceValidateInput())


def test_migrate_upgrades_active_workspace_database(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    database_path = workspace_path / ".wv" / "database.sqlite"
    _downgrade_database(database_path)

    result = run_migrate(WorkspaceMigrateInput())

    assert result.database_path == database_path
    assert result.previous_revision == "0003_session_processes"
    assert result.current_revision == get_database_head_revision()
    assert result.migrated is True


def test_migrate_is_a_no_op_for_current_workspace_database(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))

    result = run_migrate(WorkspaceMigrateInput())

    assert result.previous_revision == get_database_head_revision()
    assert result.current_revision == get_database_head_revision()
    assert result.migrated is False


def test_migrate_rejects_missing_workspace_database(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    database_path = workspace_path / ".wv" / "database.sqlite"
    database_path.unlink()

    with pytest.raises(WorkspaceError, match="database file not found"):
        run_migrate(WorkspaceMigrateInput())

    assert database_path.exists() is False


def test_migrate_rejects_unversioned_workspace_database(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    database_path = workspace_path / ".wv" / "database.sqlite"
    database_path.unlink()
    database_path.touch()

    with pytest.raises(WorkspaceError, match="no Alembic revision"):
        run_migrate(WorkspaceMigrateInput())


def test_validate_rejects_stale_database_until_migrated(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    _downgrade_database(workspace_path / ".wv" / "database.sqlite")

    with pytest.raises(WorkspaceError, match="wv workspace migrate"):
        run_validate(WorkspaceValidateInput())

    run_migrate(WorkspaceMigrateInput())

    assert run_validate(WorkspaceValidateInput()).status.database_exists is True


def test_validate_rejects_unversioned_workspace_database(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "user-config"
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_path", lambda *args, **kwargs: config_dir)
    run_initialize(WorkspaceInitializeInput(path=workspace_path))
    database_path = workspace_path / ".wv" / "database.sqlite"
    database_path.unlink()
    database_path.touch()

    with pytest.raises(WorkspaceError, match="no Alembic revision"):
        run_validate(WorkspaceValidateInput())
