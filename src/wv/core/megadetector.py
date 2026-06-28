from pathlib import Path


def load_detector(model: str, *, force_download: bool = False):
    from megadetector.detection.run_detector import load_detector as md_load_detector

    return md_load_detector(model, force_model_download=force_download)


def resolve_model_file(model: str, *, force_download: bool = False) -> Path:
    from megadetector.detection.run_detector import (
        try_download_known_detector as md_try_download_known_detector,
    )

    return Path(md_try_download_known_detector(model, force_download=force_download))


def is_gpu_available(model_file: str) -> bool:
    from megadetector.detection.run_detector import is_gpu_available as md_is_gpu_available

    return bool(md_is_gpu_available(model_file))
