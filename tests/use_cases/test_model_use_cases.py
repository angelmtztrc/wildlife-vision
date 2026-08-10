from pathlib import Path

import pytest

import wv.use_cases.models.setup as model_setup
from wv.ml.megadetector import PreparedModel
from wv.ml.speciesnet import SpeciesNetModel
from wv.use_cases.models.setup import ModelSetupInput, run as run_setup
from wv.use_cases.models.status import ModelStatusInput, run as run_status
from wv.workspace.common import WorkspaceError
from wv.workspace.workspace_config import load_workspace_config


def test_setup_activates_models_only_after_taxonomy_validation(
    configured_workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    megadetector_path = tmp_path / "megadetector.pt"
    speciesnet_path = tmp_path / "speciesnet.onnx"
    megadetector_path.write_bytes(b"megadetector")
    speciesnet_path.write_bytes(b"speciesnet")
    settings = model_setup.load_processing_config().detection
    manifest_calls = []
    monkeypatch.setattr(
        model_setup,
        "prepare_megadetector_model",
        lambda model, force_download: PreparedModel(model, megadetector_path, "CPU"),
    )
    monkeypatch.setattr(
        model_setup,
        "prepare_speciesnet_model",
        lambda model, repair: SpeciesNetModel(
            model,
            speciesnet_path,
            "digest",
            "4.0.3a",
            "CPU",
            frozenset(settings.domestic_taxon_ids),
        ),
    )
    monkeypatch.setattr(
        model_setup,
        "write_manifest",
        lambda megadetector, speciesnet: manifest_calls.append((megadetector, speciesnet)),
    )

    result = run_setup(ModelSetupInput(megadetector="v5b", speciesnet="v4.0.3a"))

    config = load_workspace_config(configured_workspace / ".wv" / "config.yml")
    assert result.megadetector_model == "MDV5B"
    assert config["processing"]["detection"]["model"] == "MDV5B"
    assert manifest_calls


def test_setup_does_not_activate_models_with_missing_domestic_taxa(
    configured_workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    model_path = tmp_path / "model.bin"
    model_path.write_bytes(b"model")
    original_config = load_workspace_config(configured_workspace / ".wv" / "config.yml")
    monkeypatch.setattr(
        model_setup,
        "prepare_megadetector_model",
        lambda model, force_download: PreparedModel(model, model_path, "CPU"),
    )
    monkeypatch.setattr(
        model_setup,
        "prepare_speciesnet_model",
        lambda model, repair: SpeciesNetModel(model, model_path, "digest", "4.0.3a", "CPU"),
    )
    monkeypatch.setattr(model_setup, "write_manifest", lambda *args: pytest.fail("unexpected manifest write"))

    with pytest.raises(WorkspaceError, match="domestic taxon IDs"):
        run_setup(ModelSetupInput(megadetector="v5b"))

    assert load_workspace_config(configured_workspace / ".wv" / "config.yml") == original_config


def test_status_reports_unprepared_selected_models(configured_workspace: Path, monkeypatch):
    monkeypatch.setattr("wv.use_cases.models.status.verify_manifest", lambda *args: None)

    result = run_status(ModelStatusInput())

    assert result.ready is False
    assert [item.status for item in result.items] == ["not ready", "not ready"]
