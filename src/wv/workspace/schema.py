from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkspaceConfigProperty:
    key: str
    expected_type: type
    required: bool = True


WORKSPACE_VERSION = 1

WORKSPACE_CONFIG_PROPERTIES = {
    "workspace.version": WorkspaceConfigProperty(
        key="workspace.version",
        expected_type=int,
    ),
    "workspace.path": WorkspaceConfigProperty(
        key="workspace.path",
        expected_type=str,
    ),
    "database.path": WorkspaceConfigProperty(
        key="database.path",
        expected_type=str,
    ),
}


def get_known_keys() -> list[str]:
    return list(WORKSPACE_CONFIG_PROPERTIES)


def build_default_config(workspace_path: Path) -> dict[str, Any]:
    resolved_workspace_path = workspace_path.resolve()
    return {
        "workspace": {
            "version": WORKSPACE_VERSION,
            "path": str(resolved_workspace_path),
        },
        "database": {
            "path": str(resolved_workspace_path / ".wv" / "database.sqlite"),
        },
    }
