from dataclasses import dataclass, field

from wv.ml.model_manifest import verify_manifest
from wv.workspace.workspace_config import load_processing_config


@dataclass(frozen=True)
class ModelStatusInput:
    pass


@dataclass(frozen=True)
class ModelStatusItem:
    engine: str
    selected: str
    device: str
    status: str


@dataclass(frozen=True)
class ModelStatusResult:
    items: list[ModelStatusItem] = field(default_factory=list)
    domestic_taxa_count: int = 0
    ready: bool = False


def run(input_data: ModelStatusInput) -> ModelStatusResult:
    """Report whether the active workspace's selected models are ready."""
    settings = load_processing_config().detection
    manifest = verify_manifest(settings.model, settings.speciesnet_model)
    ready = manifest is not None
    return ModelStatusResult(
        items=[
            ModelStatusItem(
                "MegaDetector",
                settings.model,
                manifest.megadetector_device if manifest else "-",
                "ready" if ready else "not ready",
            ),
            ModelStatusItem(
                "SpeciesNet",
                settings.speciesnet_model,
                manifest.speciesnet_device if manifest else "-",
                "ready" if ready else "not ready",
            ),
        ],
        domestic_taxa_count=len(settings.domestic_taxon_ids),
        ready=ready,
    )
