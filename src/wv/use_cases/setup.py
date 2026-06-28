from dataclasses import dataclass
from pathlib import Path

from wv.core.megadetector import is_gpu_available, load_detector, resolve_model_file

DEFAULT_MODEL = "MDV5A"


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


def _get_inference_device(detector, resolved_model: Path) -> str:
    detector_device = getattr(detector, "device", None)
    if detector_device is not None:
        normalized_device = str(detector_device).lower()
        if any(device_name in normalized_device for device_name in ("cuda", "mps", "directml")):
            return "GPU"

    return "GPU" if is_gpu_available(str(resolved_model)) else "CPU"


def run(input_data: SetupInput) -> SetupResult:
    detector = load_detector(input_data.model, force_download=input_data.force_download)
    resolved_model = resolve_model_file(input_data.model, force_download=False)

    return SetupResult(
        model=input_data.model,
        resolved_model=resolved_model,
        ready=True,
        inference_device=_get_inference_device(detector, resolved_model),
    )
