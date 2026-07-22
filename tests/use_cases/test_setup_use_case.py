from pathlib import Path

import wv.use_cases.setup as setup
from wv.ml.megadetector import PreparedModel


def test_run_reports_gpu_when_detector_device_uses_gpu(monkeypatch):
    monkeypatch.setattr(
        setup,
        "prepare_model",
        lambda model, force_download=False: PreparedModel(
            model=model,
            resolved_model=Path("/tmp/md_v5a.0.1.pt"),
            inference_device="GPU",
        ),
    )

    result = setup.run(setup.SetupInput())

    assert result.model == "MDV5A"
    assert result.ready is True
    assert result.inference_device == "GPU"


def test_run_falls_back_to_cpu_when_gpu_is_not_available(monkeypatch):
    monkeypatch.setattr(
        setup,
        "prepare_model",
        lambda model, force_download=False: PreparedModel(
            model=model,
            resolved_model=Path("/tmp/md_v5a.0.1.pt"),
            inference_device="CPU",
        ),
    )

    result = setup.run(setup.SetupInput())

    assert result.inference_device == "CPU"
