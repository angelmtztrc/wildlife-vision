from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wv.core.bursts import DEFAULT_BURST_GAP_THRESHOLD, DEFAULT_SIMILARITY_THRESHOLD
from wv.core.detection import (
    DEFAULT_AMBIGUITY_GAP,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
)
from wv.core.images import (
    DEFAULT_HIGH_LEVEL,
    DEFAULT_MEAN_THRESHOLD,
    DEFAULT_PCT_HIGH_THRESHOLD,
    DEFAULT_STD_THRESHOLD,
)
from wv.ml.megadetector import DEFAULT_MODEL


@dataclass(frozen=True)
class WorkspaceConfigProperty:
    key: str
    expected_type: type
    required: bool = True


@dataclass(frozen=True)
class OverexposedIrProcessingConfig:
    mean_threshold: float
    std_threshold: float
    high_level: int
    pct_high_threshold: float


@dataclass(frozen=True)
class BurstsProcessingConfig:
    burst_gap_threshold: int
    similarity_threshold: int


@dataclass(frozen=True)
class DetectionProcessingConfig:
    model: str
    confidence_threshold: float
    ambiguity_gap: float
    batch_size: int


@dataclass(frozen=True)
class ProcessingConfig:
    overexposed_ir: OverexposedIrProcessingConfig
    bursts: BurstsProcessingConfig
    detection: DetectionProcessingConfig


WORKSPACE_VERSION = 2

_BASE_PROPERTIES = {
    "workspace.version": WorkspaceConfigProperty("workspace.version", int),
    "workspace.path": WorkspaceConfigProperty("workspace.path", str),
    "database.path": WorkspaceConfigProperty("database.path", str),
}

WORKSPACE_CONFIG_PROPERTIES_V1 = _BASE_PROPERTIES
WORKSPACE_CONFIG_PROPERTIES_V2 = {
    **_BASE_PROPERTIES,
    "processing.overexposed_ir.mean_threshold": WorkspaceConfigProperty(
        "processing.overexposed_ir.mean_threshold", float
    ),
    "processing.overexposed_ir.std_threshold": WorkspaceConfigProperty(
        "processing.overexposed_ir.std_threshold", float
    ),
    "processing.overexposed_ir.high_level": WorkspaceConfigProperty(
        "processing.overexposed_ir.high_level", int
    ),
    "processing.overexposed_ir.pct_high_threshold": WorkspaceConfigProperty(
        "processing.overexposed_ir.pct_high_threshold", float
    ),
    "processing.bursts.burst_gap_threshold": WorkspaceConfigProperty(
        "processing.bursts.burst_gap_threshold", int
    ),
    "processing.bursts.similarity_threshold": WorkspaceConfigProperty(
        "processing.bursts.similarity_threshold", int
    ),
    "processing.detection.model": WorkspaceConfigProperty("processing.detection.model", str),
    "processing.detection.confidence_threshold": WorkspaceConfigProperty(
        "processing.detection.confidence_threshold", float
    ),
    "processing.detection.ambiguity_gap": WorkspaceConfigProperty(
        "processing.detection.ambiguity_gap", float
    ),
    "processing.detection.batch_size": WorkspaceConfigProperty(
        "processing.detection.batch_size", int
    ),
}
WORKSPACE_CONFIG_PROPERTIES = WORKSPACE_CONFIG_PROPERTIES_V2


def get_known_keys() -> list[str]:
    return list(WORKSPACE_CONFIG_PROPERTIES)


def build_default_config(workspace_path: Path) -> dict[str, Any]:
    resolved_workspace_path = workspace_path.resolve()
    return {
        "workspace": {"version": WORKSPACE_VERSION, "path": str(resolved_workspace_path)},
        "database": {"path": str(resolved_workspace_path / ".wv" / "database.sqlite")},
        "processing": {
            "overexposed_ir": {
                "mean_threshold": DEFAULT_MEAN_THRESHOLD,
                "std_threshold": DEFAULT_STD_THRESHOLD,
                "high_level": DEFAULT_HIGH_LEVEL,
                "pct_high_threshold": DEFAULT_PCT_HIGH_THRESHOLD,
            },
            "bursts": {
                "burst_gap_threshold": DEFAULT_BURST_GAP_THRESHOLD,
                "similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
            },
            "detection": {
                "model": DEFAULT_MODEL,
                "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
                "ambiguity_gap": DEFAULT_AMBIGUITY_GAP,
                "batch_size": DEFAULT_BATCH_SIZE,
            },
        },
    }
