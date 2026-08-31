from dataclasses import dataclass, field

from wv.ml.model_catalog import MEGADETECTOR_MODELS, SPECIESNET_MODELS


@dataclass(frozen=True)
class ModelListItem:
    engine: str
    alias: str
    model: str
    description: str


@dataclass(frozen=True)
class ModelListInput:
    pass


@dataclass(frozen=True)
class ModelListResult:
    items: list[ModelListItem] = field(default_factory=list)


def run(input_data: ModelListInput) -> ModelListResult:
    """List model aliases supported by the crop-classification pipeline."""
    return ModelListResult(
        items=[
            *[
                ModelListItem("MegaDetector", item.alias, item.model, item.description)
                for item in MEGADETECTOR_MODELS
            ],
            *[
                ModelListItem("SpeciesNet", item.alias, item.model, item.description)
                for item in SPECIESNET_MODELS
            ],
        ]
    )
