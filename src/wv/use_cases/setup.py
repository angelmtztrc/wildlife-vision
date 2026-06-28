from dataclasses import dataclass
from pathlib import Path

from wv.ml.megadetector import DEFAULT_MODEL, prepare_model



@dataclass(frozen=True)
class SetupInput:
    model: str = DEFAULT_MODEL
    force_download: bool = False


@dataclass(frozen=True)
class SetupResult:
    model: str
    resolved_model: Path
    ready: bool
    inference_device: str


def run(input_data: SetupInput) -> SetupResult:
    prepared_model = prepare_model(
        input_data.model,
        force_download=input_data.force_download,
    )

    return SetupResult(
        model=prepared_model.model,
        resolved_model=prepared_model.resolved_model,
        ready=True,
        inference_device=prepared_model.inference_device,
    )
