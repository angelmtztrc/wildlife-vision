"""Shared-cache model readiness manifest."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import platformdirs

from wv.core.files import get_content_digest
from wv.ml.megadetector import PreparedModel
from wv.ml.speciesnet import SpeciesNetModel


@dataclass(frozen=True)
class PreparedModelsManifest:
    megadetector_model: str
    megadetector_path: str
    megadetector_digest: str
    megadetector_device: str
    speciesnet_model: str
    speciesnet_path: str
    speciesnet_digest: str
    speciesnet_version: str
    speciesnet_device: str


def write_manifest(megadetector: PreparedModel, speciesnet: SpeciesNetModel) -> PreparedModelsManifest:
    """Atomically record verified artifacts without replacing other model pairs."""
    manifest = PreparedModelsManifest(
        megadetector_model=megadetector.model,
        megadetector_path=str(megadetector.resolved_model),
        megadetector_digest=get_content_digest(megadetector.resolved_model),
        megadetector_device=megadetector.inference_device,
        speciesnet_model=speciesnet.requested_model,
        speciesnet_path=str(speciesnet.classifier_path),
        speciesnet_digest=speciesnet.classifier_digest,
        speciesnet_version=speciesnet.model_version,
        speciesnet_device=speciesnet.inference_device,
    )
    manifests = [
        candidate
        for candidate in _load_manifests()
        if (candidate.megadetector_model, candidate.speciesnet_model)
        != (manifest.megadetector_model, manifest.speciesnet_model)
    ]
    manifests.append(manifest)
    _write_json(_manifest_path(), {"models": [asdict(candidate) for candidate in manifests]})
    return manifest


def _load_manifests() -> list[PreparedModelsManifest]:
    """Load cached model records, returning no records when the manifest is invalid."""
    path = _manifest_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        records = value.get("models") if isinstance(value, dict) else None
        if not isinstance(records, list):
            return []
        return [
            PreparedModelsManifest(**record)
            for record in records
            if isinstance(record, dict)
        ]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return []


def verify_manifest(megadetector_model: str, speciesnet_model: str) -> PreparedModelsManifest | None:
    """Return a manifest only when selected models and artifact digests match."""
    manifest = next(
        (
            candidate
            for candidate in _load_manifests()
            if (candidate.megadetector_model, candidate.speciesnet_model)
            == (megadetector_model, speciesnet_model)
        ),
        None,
    )
    if manifest is None:
        return None
    try:
        if get_content_digest(Path(manifest.megadetector_path)) != manifest.megadetector_digest:
            return None
        if get_content_digest(Path(manifest.speciesnet_path)) != manifest.speciesnet_digest:
            return None
    except OSError:
        return None
    return manifest


def remove_manifest() -> None:
    """Remove the shared readiness manifest without deleting downloaded models."""
    _manifest_path().unlink(missing_ok=True)


def _manifest_path() -> Path:
    return Path(platformdirs.user_cache_path("wildlife-vision")) / "models.json"


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".models.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
