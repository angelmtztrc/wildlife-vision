from pathlib import Path

import wv.ml.model_manifest as model_manifest
from wv.ml.megadetector import PreparedModel
from wv.ml.speciesnet import SpeciesNetModel


def _prepared_models(tmp_path: Path, suffix: str):
    megadetector_path = tmp_path / f"megadetector-{suffix}.pt"
    speciesnet_path = tmp_path / f"speciesnet-{suffix}.onnx"
    megadetector_path.write_bytes(f"megadetector-{suffix}".encode())
    speciesnet_path.write_bytes(f"speciesnet-{suffix}".encode())
    return (
        PreparedModel(f"MDV5{suffix}", megadetector_path, "CPU"),
        SpeciesNetModel(
            f"speciesnet-{suffix}",
            speciesnet_path,
            model_manifest.get_content_digest(speciesnet_path),
            suffix,
            "CPU",
        ),
    )


def test_manifest_keeps_multiple_prepared_model_pairs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(model_manifest, "_manifest_path", lambda: tmp_path / "models.json")
    first_megadetector, first_speciesnet = _prepared_models(tmp_path, "A")
    second_megadetector, second_speciesnet = _prepared_models(tmp_path, "B")

    model_manifest.write_manifest(first_megadetector, first_speciesnet)
    model_manifest.write_manifest(second_megadetector, second_speciesnet)

    assert model_manifest.verify_manifest("MDV5A", "speciesnet-A") is not None
    assert model_manifest.verify_manifest("MDV5B", "speciesnet-B") is not None


def test_manifest_rejects_changed_artifact(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(model_manifest, "_manifest_path", lambda: tmp_path / "models.json")
    megadetector, speciesnet = _prepared_models(tmp_path, "A")
    model_manifest.write_manifest(megadetector, speciesnet)
    megadetector.resolved_model.write_bytes(b"changed")

    assert model_manifest.verify_manifest("MDV5A", "speciesnet-A") is None
