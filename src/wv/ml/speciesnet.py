"""SpeciesNet isolated-runtime adapter.

SpeciesNet and MegaDetector require incompatible protobuf/ONNX versions, so
SpeciesNet executes in a dedicated cached virtual environment.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

from wv.core.logger import get_logger, get_progress
from wv.ml.megadetector import MlDetection

_SPECIESNET_VERSION = "5.0.5"
_PROGRESS_POLL_INTERVAL_SECONDS = 0.1
logger = get_logger(__name__)


@dataclass(frozen=True)
class SpeciesNetModel:
    requested_model: str
    classifier_path: Path
    classifier_digest: str
    model_version: str
    inference_device: str
    taxonomy_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SpeciesNetTaxonPrediction:
    rank: int
    taxon_id: str
    taxon_class: str | None
    taxon_order: str | None
    taxon_family: str | None
    taxon_genus: str | None
    taxon_species: str | None
    common_name: str | None
    confidence: float


@dataclass(frozen=True)
class SpeciesNetDetectionResult:
    predictions: list[SpeciesNetTaxonPrediction]
    final_label: str
    final_taxon_id: str | None
    final_taxon_rank: str | None
    final_taxon_confidence: float | None


def prepare_model(model: str, *, repair: bool = False) -> SpeciesNetModel:
    """Prepare the isolated SpeciesNet runtime and requested model artifacts."""
    if repair:
        _runtime_ready_marker().unlink(missing_ok=True)
    result = _run_worker({"operation": "prepare", "model": model})
    return _to_model(result)


def evaluate_animal_detections(
    model: str,
    requests: list[tuple[Path, int, MlDetection]],
    batch_size: int,
    latitude: float,
    longitude: float,
) -> tuple[dict[tuple[Path, int], SpeciesNetDetectionResult], SpeciesNetModel]:
    """Classify MegaDetector animal crops in SpeciesNet's isolated runtime."""
    result = _run_worker(
        {
            "operation": "evaluate",
            "model": model,
            "batch_size": batch_size,
            "latitude": latitude,
            "longitude": longitude,
            "requests": [
                {
                    "path": str(path),
                    "index": index,
                    "bbox": [
                        detection.bbox_x,
                        detection.bbox_y,
                        detection.bbox_width,
                        detection.bbox_height,
                    ],
                }
                for path, index, detection in requests
            ],
        },
        show_progress=True,
    )
    values: dict[tuple[Path, int], SpeciesNetDetectionResult] = {}
    for item in result["results"]:
        values[(Path(item["path"]), int(item["index"]))] = SpeciesNetDetectionResult(
            predictions=[SpeciesNetTaxonPrediction(**prediction) for prediction in item["predictions"]],
            final_label=item["final_label"],
            final_taxon_id=item["final_taxon_id"],
            final_taxon_rank=item["final_taxon_rank"],
            final_taxon_confidence=item["final_taxon_confidence"],
        )
    return values, _to_model(result["model"])


def _runtime_python() -> Path:
    root = Path(platformdirs.user_cache_path("wildlife-vision")) / f"speciesnet-{_SPECIESNET_VERSION}"
    python = root / "bin" / "python"
    ready = _runtime_ready_marker()
    if python.is_file() and ready.is_file():
        return python
    root.parent.mkdir(parents=True, exist_ok=True)
    _run(["uv", "venv", "--python", "3.12", str(root)])
    _run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(root / "bin" / "python"),
            f"speciesnet=={_SPECIESNET_VERSION}",
            "onnx==1.16.0",
            "pycountry>=24.6.1",
        ]
    )
    ready.touch()
    return root / "bin" / "python"


def _runtime_ready_marker() -> Path:
    return Path(platformdirs.user_cache_path("wildlife-vision")) / f"speciesnet-{_SPECIESNET_VERSION}" / ".wv-ready"


def _run_worker(payload: dict, *, show_progress: bool = False) -> dict:
    with tempfile.TemporaryDirectory(prefix="wv-speciesnet-") as directory:
        root = Path(directory)
        request_path = root / "request.json"
        result_path = root / "result.json"
        progress_path = root / "progress.json"
        if show_progress:
            payload = {**payload, "progress_path": str(progress_path)}
        request_path.write_text(json.dumps(payload), encoding="utf-8")
        environment = os.environ | {"PYTHONPATH": str(Path(__file__).parents[2])}
        command = [
            str(_runtime_python()),
            "-m",
            "wv.ml.speciesnet_worker",
            str(request_path),
            str(result_path),
        ]
        if show_progress:
            _run_worker_with_progress(command, environment, progress_path)
        else:
            _run(command, environment)
        return json.loads(result_path.read_text(encoding="utf-8"))


def _run_worker_with_progress(
    command: list[str], environment: dict[str, str], progress_path: Path
) -> None:
    """Run an evaluation worker while rendering its atomically published progress."""
    with tempfile.TemporaryDirectory(prefix="wv-speciesnet-output-") as output_directory:
        output_root = Path(output_directory)
        stdout_path = output_root / "stdout.log"
        stderr_path = output_root / "stderr.log"
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=environment)
            with get_progress() as progress:
                task = progress.add_task("Loading SpeciesNet model", total=None)
                while process.poll() is None:
                    _update_progress(progress, task, progress_path)
                    time.sleep(_PROGRESS_POLL_INTERVAL_SECONDS)
                _update_progress(progress, task, progress_path)

        stdout = stdout_path.read_text(encoding="utf-8").strip()
        stderr = stderr_path.read_text(encoding="utf-8").strip()
        if process.returncode != 0:
            detail = stderr or stdout or "unknown error"
            raise RuntimeError(f"SpeciesNet evaluation failed: {detail}")
        if stdout:
            logger.debug("Captured stdout from SpeciesNet worker:\n%s", stdout)
        if stderr:
            logger.debug("Captured stderr from SpeciesNet worker:\n%s", stderr)


def _update_progress(progress, task: int, progress_path: Path) -> None:
    status = _read_progress(progress_path)
    if status is None:
        return
    phase = status["phase"]
    if phase == "loading_model":
        progress.update(task, description="Loading SpeciesNet model", total=None)
        return
    if phase == "classifying":
        progress.update(
            task,
            description="Classifying animal detections with SpeciesNet",
            total=status["total"],
            completed=status["completed"],
        )
        return
    progress.update(
        task,
        description="SpeciesNet classification complete",
        total=status["total"],
        completed=status["total"],
    )


def _read_progress(progress_path: Path) -> dict[str, int | str] | None:
    try:
        value = json.loads(progress_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    phase = value.get("phase")
    completed = value.get("completed")
    total = value.get("total")
    if phase not in {"loading_model", "classifying", "complete"}:
        return None
    if not isinstance(completed, int) or not isinstance(total, int) or completed < 0 or total < 0:
        return None
    return {"phase": phase, "completed": min(completed, total), "total": total}


def _run(command: list[str], environment: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, text=True, capture_output=True, env=environment)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise RuntimeError(f"SpeciesNet runtime setup failed: {detail}")


def _to_model(value: dict) -> SpeciesNetModel:
    return SpeciesNetModel(
        requested_model=value["requested_model"],
        classifier_path=Path(value["classifier_path"]),
        classifier_digest=value["classifier_digest"],
        model_version=value["model_version"],
        inference_device=value["inference_device"],
        taxonomy_ids=frozenset(value.get("taxonomy_ids", [])),
    )
