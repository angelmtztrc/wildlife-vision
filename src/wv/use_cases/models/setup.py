from dataclasses import dataclass
from pathlib import Path

from wv.ml.megadetector import prepare_model as prepare_megadetector_model
from wv.ml.model_catalog import resolve_megadetector_model, resolve_speciesnet_model
from wv.ml.model_manifest import write_manifest
from wv.ml.speciesnet import prepare_model as prepare_speciesnet_model
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import (
    load_processing_config,
    load_workspace_config,
    require_workspace_path,
    set_config_property,
    write_workspace_config,
)


@dataclass(frozen=True)
class ModelSetupInput:
    megadetector: str | None = None
    speciesnet: str | None = None
    repair: bool = False


@dataclass(frozen=True)
class ModelSetupResult:
    megadetector_model: str
    megadetector_path: Path
    megadetector_device: str
    speciesnet_model: str
    speciesnet_path: Path
    speciesnet_version: str
    speciesnet_device: str
    domestic_taxa_count: int


def run(input_data: ModelSetupInput) -> ModelSetupResult:
    """Prepare and atomically activate selected models for the active workspace."""
    workspace_path = require_workspace_path()
    settings = load_processing_config().detection
    megadetector_model = resolve_megadetector_model(input_data.megadetector or settings.model)
    speciesnet_model = resolve_speciesnet_model(input_data.speciesnet or settings.speciesnet_model)

    megadetector = prepare_megadetector_model(
        megadetector_model, force_download=input_data.repair
    )
    speciesnet = prepare_speciesnet_model(speciesnet_model, repair=input_data.repair)
    missing_taxa = set(settings.domestic_taxon_ids).difference(speciesnet.taxonomy_ids)
    if missing_taxa:
        raise WorkspaceError(
            "Configured domestic taxon IDs are absent from the selected SpeciesNet taxonomy: "
            + ", ".join(sorted(missing_taxa))
        )

    write_manifest(megadetector, speciesnet)
    config = load_workspace_config()
    set_config_property(config, "processing.detection.model", megadetector.model)
    set_config_property(config, "processing.detection.speciesnet_model", speciesnet.requested_model)
    write_workspace_config(config)

    return ModelSetupResult(
        megadetector_model=megadetector.model,
        megadetector_path=megadetector.resolved_model,
        megadetector_device=megadetector.inference_device,
        speciesnet_model=speciesnet.requested_model,
        speciesnet_path=speciesnet.classifier_path,
        speciesnet_version=speciesnet.model_version,
        speciesnet_device=speciesnet.inference_device,
        domestic_taxa_count=len(settings.domestic_taxon_ids),
    )
