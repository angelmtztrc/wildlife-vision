"""Supported model aliases and pipeline compatibility rules."""

from dataclasses import dataclass

from wv.ml.megadetector import DEFAULT_MODEL
from wv.workspace.schema import DEFAULT_SPECIESNET_MODEL


@dataclass(frozen=True)
class ModelCatalogEntry:
    alias: str
    model: str
    description: str


MEGADETECTOR_MODELS = (
    ModelCatalogEntry("v5a", DEFAULT_MODEL, "MegaDetector V5A wildlife detector."),
    ModelCatalogEntry("v5b", "MDV5B", "MegaDetector V5B wildlife detector."),
)
SPECIESNET_MODELS = (
    ModelCatalogEntry(
        "v4.0.3a",
        DEFAULT_SPECIESNET_MODEL,
        "SpeciesNet crop classifier for MegaDetector animal boxes.",
    ),
)


def resolve_megadetector_model(value: str) -> str:
    """Resolve a supported MegaDetector alias while allowing model paths."""
    return _resolve(value, MEGADETECTOR_MODELS, "MegaDetector")


def resolve_speciesnet_model(value: str) -> str:
    """Resolve a supported crop-classifier alias while allowing model paths."""
    if value.strip().lower() == "v4.0.3b":
        raise ValueError(
            "SpeciesNet v4.0.3b is a full-image classifier and is incompatible with crop classification."
        )
    return _resolve(value, SPECIESNET_MODELS, "SpeciesNet")


def _resolve(value: str, entries: tuple[ModelCatalogEntry, ...], model_type: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{model_type} model must not be empty.")
    for entry in entries:
        if normalized.lower() == entry.alias:
            return entry.model
    return normalized
