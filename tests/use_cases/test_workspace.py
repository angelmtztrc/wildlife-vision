import stat
import sqlite3
from pathlib import Path

import platformdirs
import pytest

from wv.use_cases.workspace.initialize import WorkspaceInitializeInput, run as run_initialize
from wv.use_cases.workspace.show import WorkspaceShowInput, run as run_show
from wv.use_cases.workspace.validate import WorkspaceValidateInput, run as run_validate
from wv.workspace.common import WorkspaceError


def _get_table_names(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    return {row[0] for row in rows}


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
