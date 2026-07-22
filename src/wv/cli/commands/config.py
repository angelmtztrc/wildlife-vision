from typing import Annotated, Any

import typer
import yaml

from wv.core.logger import get_logger
from wv.use_cases.config import run_get, run_init, run_path, run_reset, run_set, run_validate
from wv.workspace.common import WorkspaceError
from wv.workspace.schema import get_known_keys

app = typer.Typer(help="Manage workspace configuration.")

logger = get_logger(__name__)


def _complete_key(incomplete: str) -> list[str]:
    return [key for key in get_known_keys() if key.startswith(incomplete)]


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, sort_keys=False).strip()
    return str(value)


@app.command("init")
def init_config():
    try:
        result = run_init()
    except WorkspaceError as exc:
        logger.error("Config initialization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace config initialized at %s", result.path)
    return None


@app.command("get")
def get_config(
    key: Annotated[
        str,
        typer.Argument(help="Known workspace config key.", autocompletion=_complete_key),
    ],
):
    try:
        result = run_get(key)
    except WorkspaceError as exc:
        logger.error("Config get failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(_render_value(result.value))
    return None


@app.command("set")
def set_config(
    key: Annotated[
        str,
        typer.Argument(help="Known workspace config key.", autocompletion=_complete_key),
    ],
    value: Annotated[str, typer.Argument(help="Value to assign to the config key.")],
):
    try:
        result = run_set(key, value)
    except WorkspaceError as exc:
        logger.error("Config set failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Set %s=%s", result.key, _render_value(result.value))
    return None


@app.command("reset")
def reset_config(
    key: Annotated[
        str,
        typer.Argument(help="Known workspace config key.", autocompletion=_complete_key),
    ],
):
    try:
        result = run_reset(key)
    except WorkspaceError as exc:
        logger.error("Config reset failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Reset %s=%s", result.key, _render_value(result.value))
    return None


@app.command("validate")
def validate_config():
    try:
        result = run_validate()
    except WorkspaceError as exc:
        logger.error("Config validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace config is valid at %s", result.path)
    return None


@app.command("path")
def config_path():
    try:
        result = run_path()
    except WorkspaceError as exc:
        logger.error("Config path failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(result.path)
    return None
