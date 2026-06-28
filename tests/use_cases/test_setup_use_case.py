from pathlib import Path

import wv.use_cases.setup as setup


class FakeCudaDetector:
    device = "cuda:0"


class FakeCpuDetector:
    device = "cpu"


def test_run_reports_gpu_when_detector_device_uses_gpu(monkeypatch):
    monkeypatch.setattr(setup, "load_detector", lambda model, force_download=False: FakeCudaDetector())
    monkeypatch.setattr(
        setup,
        "resolve_model_file",
        lambda model, force_download=False: Path("/tmp/md_v5a.0.1.pt"),
    )

    result = setup.run(setup.SetupInput())

    assert result.model == "MDV5A"
    assert result.ready is True
    assert result.inference_device == "GPU"


def test_run_falls_back_to_cpu_when_gpu_is_not_available(monkeypatch):
    monkeypatch.setattr(setup, "load_detector", lambda model, force_download=False: FakeCpuDetector())
    monkeypatch.setattr(
        setup,
        "resolve_model_file",
        lambda model, force_download=False: Path("/tmp/md_v5a.0.1.pt"),
    )
    monkeypatch.setattr(setup, "is_gpu_available", lambda model_file: False)

    result = setup.run(setup.SetupInput())

    assert result.inference_device == "CPU"
