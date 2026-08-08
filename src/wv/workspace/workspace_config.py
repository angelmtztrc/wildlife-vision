import copy
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from wv.core.bursts import validate_burst_thresholds
from wv.core.detection import validate_detection_settings
from wv.core.files import SymlinkPathError, ensure_not_symlink
from wv.core.images import validate_exposure_thresholds
from wv.workspace.common import WORKSPACE_CONFIG_NAME, WORKSPACE_DATABASE_NAME, WORKSPACE_METADATA_DIRNAME, WorkspaceError
from wv.workspace.config import get_workspace_path
from wv.workspace.schema import (
    BurstsProcessingConfig,
    DetectionProcessingConfig,
    OverexposedIrProcessingConfig,
    ProcessingConfig,
    WORKSPACE_CONFIG_PROPERTIES,
    WORKSPACE_CONFIG_PROPERTIES_V1,
    WORKSPACE_VERSION,
    build_default_config,
)


def get_workspace_metadata_dir(workspace_path: Path) -> Path:
    return workspace_path / WORKSPACE_METADATA_DIRNAME


def require_workspace_path() -> Path:
    workspace_path = get_workspace_path()
    if workspace_path is None:
        raise WorkspaceError("No workspace configured.")
    try:
        ensure_not_symlink(workspace_path)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not workspace_path.is_dir():
        raise WorkspaceError(f"Workspace path does not exist: {workspace_path}")
    return workspace_path


def get_workspace_config_path() -> Path:
    return get_workspace_metadata_dir(require_workspace_path()) / WORKSPACE_CONFIG_NAME


def get_workspace_database_path(workspace_path: Path) -> Path:
    return get_workspace_metadata_dir(workspace_path) / WORKSPACE_DATABASE_NAME


def require_workspace_database_path(workspace_path: Path | None = None) -> Path:
    active_workspace_path = workspace_path or require_workspace_path()
    try:
        ensure_not_symlink(active_workspace_path)
        metadata_path = get_workspace_metadata_dir(active_workspace_path)
        database_path = metadata_path / WORKSPACE_DATABASE_NAME
        ensure_not_symlink(metadata_path)
        ensure_not_symlink(database_path)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not database_path.is_file():
        raise WorkspaceError(f"Workspace database file not found: {database_path}")
    return database_path


def load_workspace_config(config_file: Path | None = None) -> dict[str, Any]:
    resolved_config_file = config_file or get_workspace_config_path()
    try:
        ensure_not_symlink(resolved_config_file.parent)
        ensure_not_symlink(resolved_config_file)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    if not resolved_config_file.exists():
        raise WorkspaceError(f"Workspace config file not found: {resolved_config_file}")
    try:
        with resolved_config_file.open("r", encoding="utf-8") as file_handle:
            value = yaml.safe_load(file_handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise WorkspaceError(f"Unable to read workspace config: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceError("Workspace config file must contain a YAML mapping.")
    return value


def write_workspace_config(value: dict[str, Any], config_file: Path | None = None) -> Path:
    resolved_config_file = config_file or get_workspace_config_path()
    try:
        ensure_not_symlink(resolved_config_file.parent)
        ensure_not_symlink(resolved_config_file)
    except SymlinkPathError as exc:
        raise WorkspaceError(str(exc)) from exc
    resolved_config_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=resolved_config_file.parent, prefix=f".{resolved_config_file.name}.", suffix=".tmp"
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file_handle:
            yaml.safe_dump(value, file_handle, sort_keys=False)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary_path, resolved_config_file)
        directory_descriptor = os.open(resolved_config_file.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except (OSError, yaml.YAMLError) as exc:
        raise WorkspaceError(f"Unable to write workspace config: {exc}") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return resolved_config_file


def initialize_workspace_config(workspace_path: Path, config_file: Path | None = None) -> Path:
    return write_workspace_config(build_default_config(workspace_path), config_file=config_file)


def get_config_property(value: dict[str, Any], key: str, default: Any = None) -> Any:
    current_value: Any = value
    for part in key.split("."):
        if not isinstance(current_value, dict):
            return default
        current_value = current_value.get(part)
    return default if current_value is None else current_value


def set_config_property(value: dict[str, Any], key: str, property_value: Any) -> dict[str, Any]:
    current_value = value
    parts = key.split(".")
    for part in parts[:-1]:
        nested_value = current_value.get(part)
        if not isinstance(nested_value, dict):
            nested_value = {}
            current_value[part] = nested_value
        current_value = nested_value
    current_value[parts[-1]] = property_value
    return value


def reset_config_property(value: dict[str, Any], key: str, workspace_path: Path) -> dict[str, Any]:
    return set_config_property(value, key, get_config_property(build_default_config(workspace_path), key))


def validate_known_key(key: str) -> None:
    if key not in WORKSPACE_CONFIG_PROPERTIES:
        raise WorkspaceError(f"Unknown workspace config key: {key}")


def _workspace_version(value: dict[str, Any]) -> int:
    version = get_config_property(value, "workspace.version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise WorkspaceError("Invalid workspace config value for workspace.version: expected integer")
    return version


def _validate_base_config(value: dict[str, Any], workspace_path: Path, properties: dict) -> None:
    expected_workspace_path = workspace_path.resolve()
    for key, definition in properties.items():
        property_value = get_config_property(value, key)
        if property_value is None:
            if definition.required:
                raise WorkspaceError(f"Missing required workspace config key: {key}")
            continue
        if definition.expected_type is int:
            valid = isinstance(property_value, int) and not isinstance(property_value, bool)
        elif definition.expected_type is float:
            valid = isinstance(property_value, (int, float)) and not isinstance(property_value, bool)
        else:
            valid = isinstance(property_value, definition.expected_type)
        if not valid:
            raise WorkspaceError(f"Invalid workspace config value for {key}: expected {definition.expected_type.__name__}")
    if Path(get_config_property(value, "workspace.path")).resolve() != expected_workspace_path:
        raise WorkspaceError("Invalid workspace config value for workspace.path: expected active workspace path")
    if Path(get_config_property(value, "database.path")).resolve() != get_workspace_database_path(expected_workspace_path):
        raise WorkspaceError("Invalid workspace config value for database.path: expected workspace database path")


def validate_workspace_config(value: dict[str, Any], workspace_path: Path) -> None:
    version = _workspace_version(value)
    if version == 1:
        _validate_base_config(value, workspace_path, WORKSPACE_CONFIG_PROPERTIES_V1)
        return
    if version != WORKSPACE_VERSION:
        raise WorkspaceError(f"Invalid workspace config value for workspace.version: expected {WORKSPACE_VERSION}")
    _validate_base_config(value, workspace_path, WORKSPACE_CONFIG_PROPERTIES)
    try:
        settings = _processing_config(value)
        validate_exposure_thresholds(settings.overexposed_ir.mean_threshold, settings.overexposed_ir.std_threshold, settings.overexposed_ir.high_level, settings.overexposed_ir.pct_high_threshold)
        validate_burst_thresholds(settings.bursts.burst_gap_threshold, settings.bursts.similarity_threshold)
        validate_detection_settings(settings.detection.confidence_threshold, settings.detection.ambiguity_gap, settings.detection.batch_size)
    except ValueError as exc:
        raise WorkspaceError(f"Invalid workspace processing config: {exc}") from exc
    if not settings.detection.model.strip():
        raise WorkspaceError("Invalid workspace config value for processing.detection.model: expected non-empty string")


def _processing_config(value: dict[str, Any]) -> ProcessingConfig:
    return ProcessingConfig(
        overexposed_ir=OverexposedIrProcessingConfig(
            mean_threshold=float(get_config_property(value, "processing.overexposed_ir.mean_threshold")),
            std_threshold=float(get_config_property(value, "processing.overexposed_ir.std_threshold")),
            high_level=get_config_property(value, "processing.overexposed_ir.high_level"),
            pct_high_threshold=float(get_config_property(value, "processing.overexposed_ir.pct_high_threshold")),
        ),
        bursts=BurstsProcessingConfig(
            burst_gap_threshold=get_config_property(value, "processing.bursts.burst_gap_threshold"),
            similarity_threshold=get_config_property(value, "processing.bursts.similarity_threshold"),
        ),
        detection=DetectionProcessingConfig(
            model=get_config_property(value, "processing.detection.model"),
            confidence_threshold=float(get_config_property(value, "processing.detection.confidence_threshold")),
            ambiguity_gap=float(get_config_property(value, "processing.detection.ambiguity_gap")),
            batch_size=get_config_property(value, "processing.detection.batch_size"),
        ),
    )


def load_processing_config(config_file: Path | None = None, workspace_path: Path | None = None) -> ProcessingConfig:
    active_workspace_path = workspace_path or require_workspace_path()
    value = load_workspace_config(config_file)
    validate_workspace_config(value, active_workspace_path)
    if _workspace_version(value) != WORKSPACE_VERSION:
        raise WorkspaceError("Workspace config is version 1. Run 'wv workspace migrate'.")
    return _processing_config(value)


def migrate_workspace_config_v1_to_v2(value: dict[str, Any], workspace_path: Path) -> dict[str, Any]:
    if _workspace_version(value) != 1:
        raise WorkspaceError("Workspace config migration requires version 1.")
    validate_workspace_config(value, workspace_path)
    migrated = copy.deepcopy(value)
    defaults = build_default_config(workspace_path)
    processing = migrated.get("processing")
    if processing is None:
        processing = {}
        migrated["processing"] = processing
    if not isinstance(processing, dict):
        raise WorkspaceError("Invalid workspace config value for processing: expected mapping")
    for group, default_group in defaults["processing"].items():
        group_value = processing.get(group)
        if group_value is None:
            processing[group] = copy.deepcopy(default_group)
        elif not isinstance(group_value, dict):
            raise WorkspaceError(f"Invalid workspace config value for processing.{group}: expected mapping")
        else:
            for key, default_value in default_group.items():
                group_value.setdefault(key, default_value)
    migrated["workspace"]["version"] = WORKSPACE_VERSION
    validate_workspace_config(migrated, workspace_path)
    return migrated
