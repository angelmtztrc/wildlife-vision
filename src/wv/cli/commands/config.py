from typing import Annotated, Any

import typer
import yaml

from wv.core.logger import get_logger
from wv.use_cases.config.get_value import GetConfigValueInput, run as run_get_config_value
from wv.use_cases.config.initialize import ConfigInitializeInput, run as run_initialize_config
from wv.use_cases.config.reset_value import ResetConfigValueInput, run as run_reset_config_value
from wv.use_cases.config.set_value import SetConfigValueInput, run as run_set_config_value
from wv.use_cases.config.show_path import ShowConfigPathInput, run as run_show_config_path
from wv.use_cases.config.validate import ValidateConfigInput, run as run_validate_config
from wv.workspace.common import WorkspaceError
from wv.workspace.schema import get_known_keys

app = typer.Typer(help="Manage configuration for the active workspace.")

logger = get_logger(__name__)


def _complete_key(incomplete: str) -> list[str]:
    return [key for key in get_known_keys() if key.startswith(incomplete)]


def _render_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, sort_keys=False).strip()
    return str(value)


@app.command("init")
def init_config():
    """Create the default config when the active workspace has no config file."""
    try:
        result = run_initialize_config(ConfigInitializeInput())
    except WorkspaceError as exc:
        logger.error("Config initialization failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace config initialized at %s", result.path)
    return None


@app.command("get")
def get_config(
    key: Annotated[
        str,
        typer.Argument(help="Known dot-separated workspace config key.", autocompletion=_complete_key),
    ],
):
    """Print one value from the active workspace config."""
    try:
        result = run_get_config_value(GetConfigValueInput(key=key))
    except WorkspaceError as exc:
        logger.error("Config get failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(_render_value(result.value))
    return None


@app.command("set")
def set_config(
    key: Annotated[
        str,
        typer.Argument(help="Known dot-separated workspace config key.", autocompletion=_complete_key),
    ],
    value: Annotated[str, typer.Argument(help="YAML value to assign to the config key.")],
):
    """Set and validate one value in the active workspace config."""
    try:
        result = run_set_config_value(SetConfigValueInput(key=key, raw_value=value))
    except WorkspaceError as exc:
        logger.error("Config set failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Set %s=%s", result.key, _render_value(result.value))
    return None


@app.command("reset")
def reset_config(
    key: Annotated[
        str,
        typer.Argument(help="Known dot-separated workspace config key.", autocompletion=_complete_key),
    ],
):
    """Reset one active workspace setting to its built-in default."""
    try:
        result = run_reset_config_value(ResetConfigValueInput(key=key))
    except WorkspaceError as exc:
        logger.error("Config reset failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Reset %s=%s", result.key, _render_value(result.value))
    return None


@app.command("validate")
def validate_config():
    """Validate the active workspace config and processing settings."""
    try:
        result = run_validate_config(ValidateConfigInput())
    except WorkspaceError as exc:
        logger.error("Config validation failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done("Workspace config is valid at %s", result.path)
    return None


@app.command("path")
def config_path():
    """Print the active workspace config path."""
    try:
        result = run_show_config_path(ShowConfigPathInput())
    except WorkspaceError as exc:
        logger.error("Config path failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(result.path)
    return None
