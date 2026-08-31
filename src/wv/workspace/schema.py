from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wv.core.bursts import DEFAULT_BURST_GAP_THRESHOLD, DEFAULT_SIMILARITY_THRESHOLD
from wv.core.detection import DEFAULT_BATCH_SIZE
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
    speciesnet_model: str
    batch_size: int
    domestic_taxon_ids: list[str]


@dataclass(frozen=True)
class ProcessingConfig:
    overexposed_ir: OverexposedIrProcessingConfig
    bursts: BurstsProcessingConfig
    detection: DetectionProcessingConfig


WORKSPACE_VERSION = 3

DEFAULT_SPECIESNET_MODEL = "kaggle:google/speciesnet/pyTorch/v4.0.3a/1"
DEFAULT_DOMESTIC_TAXON_IDS = [
    "4173d2d9-1d0e-42cd-bf66-f295e62a7c08",
    "cae9534f-f302-4229-9e11-b91138333d92",
    "aca65aaa-8c6d-4b69-94de-842b08b13bd6",
    "c964ec4e-4ced-4e7c-9207-fbb81444d32a",
    "5bb21a74-92cf-4eb8-b32c-a3b4e6f49d36",
    "189cdd40-b83d-48d1-a4fa-e43a104f2a23",
    "0de8422e-f59d-4802-9e93-ab8559e43e55",
    "c150a21e-952d-4665-8a62-a319841c5a56",
    "3d80f1d6-b1df-4966-9ff4-94053c7a902a",
    "9212982e-8a58-4775-a6ac-e9a43110d8f5",
    "8a766598-fcfe-4c06-b899-7213f9b20dfa",
    "5109acb4-e503-4147-a175-a3c6aa71f1e3",
    "b1e08fbb-d8b6-47b1-8559-a39c73f1f0ae",
    "608f0305-b94a-4f39-b445-654fbb07ba73",
    "a4f23daa-a66d-483c-94d4-3132aea33283",
]

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
WORKSPACE_CONFIG_PROPERTIES_V3 = {
    **_BASE_PROPERTIES,
    "processing.overexposed_ir.mean_threshold": WorkspaceConfigProperty("processing.overexposed_ir.mean_threshold", float),
    "processing.overexposed_ir.std_threshold": WorkspaceConfigProperty("processing.overexposed_ir.std_threshold", float),
    "processing.overexposed_ir.high_level": WorkspaceConfigProperty("processing.overexposed_ir.high_level", int),
    "processing.overexposed_ir.pct_high_threshold": WorkspaceConfigProperty("processing.overexposed_ir.pct_high_threshold", float),
    "processing.bursts.burst_gap_threshold": WorkspaceConfigProperty("processing.bursts.burst_gap_threshold", int),
    "processing.bursts.similarity_threshold": WorkspaceConfigProperty("processing.bursts.similarity_threshold", int),
    "processing.detection.model": WorkspaceConfigProperty("processing.detection.model", str),
    "processing.detection.speciesnet_model": WorkspaceConfigProperty("processing.detection.speciesnet_model", str),
    "processing.detection.batch_size": WorkspaceConfigProperty("processing.detection.batch_size", int),
    "processing.detection.domestic_taxon_ids": WorkspaceConfigProperty("processing.detection.domestic_taxon_ids", list),
}
WORKSPACE_CONFIG_PROPERTIES = WORKSPACE_CONFIG_PROPERTIES_V3


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
                "speciesnet_model": DEFAULT_SPECIESNET_MODEL,
                "batch_size": DEFAULT_BATCH_SIZE,
                "domestic_taxon_ids": list(DEFAULT_DOMESTIC_TAXON_IDS),
            },
        },
    }
