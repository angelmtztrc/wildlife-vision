import json
from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from wv.core.detection import (
    classify_detections,
    validate_detection_settings,
    CLASSIFICATION_GATE,
    MINIMUM_DETECTION_THRESHOLD,
    SpeciesNetClassification,
)
from wv.core.files import get_content_digest, is_allowed_image_file, move_file_with_staged_copy
from wv.core.session import get_detection_path
from wv.ml.megadetector import MlImageResult, iter_evaluate_images, resolve_model
from wv.ml.model_manifest import verify_manifest
from wv.ml.speciesnet import evaluate_animal_detections
from wv.domain.session import (
    ImageDetectionResult,
    ImageObjectDetection,
    ImageTaxonPrediction,
    SessionImage,
    SessionProcess,
    SessionProcessImagePlan,
)
from wv.persistence.repositories import (
    ImageDetectionResultRepository,
    MonitoringSiteRepository,
    SessionImageRepository,
    SessionProcessImagePlanRepository,
    SessionProcessRepository,
)
from wv.persistence.sql_session import sql_session_scope
from ._shared import (
    ManagedSession,
    SessionProcessError,
    _exclusive_session_lock,
    _relative_path,
    _resolve_session_path,
    canonical_process_parameters,
    resolve_managed_session,
    resolve_process_parameters,
    utc_now,
    validate_process_attempt,
    validate_process_parameters,
)
from wv.workspace.workspace_config import load_processing_config

PROCESS_NAME = "detect_content"
ALGORITHM_VERSION = 3
@dataclass(frozen=True)
class SessionDetectContentInput:
    session_id: str
    model: str | None = None
    speciesnet_model: str | None = None
    batch_size: int | None = None
    dry_run: bool = False
    recover: bool = False


@dataclass(frozen=True)
class SessionDetectContentResult:
    session_id: str
    process: SessionProcess | None
    files_discovered: int = 0
    files_evaluated: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    files_animal: int = 0
    files_human: int = 0
    files_vehicle: int = 0
    files_domestic: int = 0
    files_empty: int = 0
    files_other: int = 0
    destination: Path = Path()
    dry_run: bool = False


@dataclass
class _DetectContentSummary:
    files_discovered: int = 0
    files_evaluated: int = 0
    files_moved: int = 0
    files_ignored: int = 0
    files_failed: int = 0
    files_replaced: int = 0
    files_animal: int = 0
    files_human: int = 0
    files_vehicle: int = 0
    files_domestic: int = 0
    files_empty: int = 0
    files_other: int = 0
    destination: Path = Path()
    dry_run: bool = False


def _parameters_json(input_data: SessionDetectContentInput) -> str:
    return canonical_process_parameters(
        {
            "algorithm_version": ALGORITHM_VERSION,
            "batch_size": input_data.batch_size,
            "model": input_data.model,
            "speciesnet_model": input_data.speciesnet_model,
            "minimum_detection_threshold": MINIMUM_DETECTION_THRESHOLD,
            "classification_gate": CLASSIFICATION_GATE,
        }
    )


def _resolve_input(
    managed_session: ManagedSession, input_data: SessionDetectContentInput
) -> SessionDetectContentInput:
    settings = load_processing_config()
    with sql_session_scope(managed_session.database_path) as sql_session:
        process = SessionProcessRepository(sql_session).get_optional(
            managed_session.session.id, PROCESS_NAME
        )
    values = resolve_process_parameters(
        process,
        PROCESS_NAME,
        {
            "model": input_data.model,
            "speciesnet_model": input_data.speciesnet_model,
            "batch_size": input_data.batch_size,
        },
        {
            "model": settings.detection.model,
            "speciesnet_model": settings.detection.speciesnet_model,
            "batch_size": settings.detection.batch_size,
        },
    )
    return replace(
        input_data,
        model=str(values["model"]),
        speciesnet_model=str(values["speciesnet_model"]),
        batch_size=int(values["batch_size"]),
    )


def _load_candidates(managed_session: ManagedSession) -> tuple[list[SessionImage], int, int]:
    with sql_session_scope(managed_session.database_path) as sql_session:
        images = SessionImageRepository(sql_session).list_for_session(
            managed_session.session.id
        )
    by_path = {image.current_relative_path: image for image in images}
    candidates: list[SessionImage] = []
    discovered = 0
    ignored = 0
    for path in sorted(managed_session.init_path.iterdir()):
        discovered += 1
        if not path.is_file() or not is_allowed_image_file(path):
            ignored += 1
            continue
        relative_path = _relative_path(managed_session.session_path, path)
        image = by_path.get(relative_path)
        if image is None or image.state != "init":
            raise SessionProcessError(f"Supported image is not tracked in init: {path}")
        _require_content(path, image.content_digest, image.content_size_bytes)
        candidates.append(image)
    return candidates, discovered, ignored


def _require_content(path: Path, content_digest: str, content_size_bytes: int) -> None:
    if not path.is_file() or path.stat().st_size != content_size_bytes:
        raise SessionProcessError(f"Image does not match persisted inventory: {path}")
    if get_content_digest(path) != content_digest:
        raise SessionProcessError(f"Image does not match persisted inventory: {path}")


def _increment_label(result: _DetectContentSummary, label: str) -> None:
    setattr(result, f"files_{label}", getattr(result, f"files_{label}") + 1)


def _build_plan(
    managed_session: ManagedSession,
    input_data: SessionDetectContentInput,
    candidates: list[SessionImage],
) -> tuple[list[SessionProcessImagePlan], list[ImageDetectionResult], _DetectContentSummary, str]:
    if not candidates:
        return [], [], _DetectContentSummary(), canonical_process_parameters({"schema_version": 2})

    settings = load_processing_config()
    if verify_manifest(str(input_data.model), str(input_data.speciesnet_model)) is None:
        raise SessionProcessError("Selected models are not ready. Run 'wv models setup'.")
    resolved_model = resolve_model(input_data.model)
    execution_details = canonical_process_parameters(
        {
            "schema_version": 2,
            "megadetector_version": version("megadetector"),
            "model": {
                "requested": resolved_model.requested_model,
                "resolved_path": str(resolved_model.resolved_path),
                "content_digest": resolved_model.content_digest,
                "size_bytes": resolved_model.content_size_bytes,
            },
        }
    )
    source_paths = [
        _resolve_session_path(managed_session.session_path, image.current_relative_path)
        for image in candidates
    ]
    inference_results = iter_evaluate_images(
        model=str(resolved_model.resolved_path),
        image_paths=source_paths,
        confidence_threshold=MINIMUM_DETECTION_THRESHOLD,
        batch_size=input_data.batch_size,
    )

    result = _DetectContentSummary(
        files_discovered=len(candidates),
        files_evaluated=0,
        destination=get_detection_path(managed_session.session_path),
        dry_run=input_data.dry_run,
    )
    plans: list[SessionProcessImagePlan] = []
    analysis_results: list[ImageDetectionResult] = []
    planned_at = utc_now()
    inference_by_path: dict[Path, MlImageResult] = {}
    for source_path, inference_result in zip(source_paths, inference_results, strict=True):
        _validate_inference_result(inference_result, source_path)
        if inference_result.failure:
            raise SessionProcessError(f"Detection failed for {source_path}: {inference_result.failure}")
        inference_by_path[source_path] = inference_result

    with sql_session_scope(managed_session.database_path) as sql_session:
        monitoring_site = MonitoringSiteRepository(sql_session).get(
            managed_session.session.monitoring_site_id
        )
    species_requests = [
        (source_path, index, detection)
        for source_path, inference_result in inference_by_path.items()
        for index, detection in enumerate(inference_result.detections)
        if detection.label == "animal" and detection.confidence >= CLASSIFICATION_GATE
    ]
    species_results = {}
    species_model = None
    if species_requests:
        try:
            species_results, species_model = evaluate_animal_detections(
                str(input_data.speciesnet_model),
                species_requests,
                int(input_data.batch_size),
                monitoring_site.latitude,
                monitoring_site.longitude,
            )
        except Exception as exc:
            raise SessionProcessError(f"SpeciesNet classification failed: {exc}") from exc
        execution_details = canonical_process_parameters(
            {
                **json.loads(execution_details),
                "speciesnet": {
                    "requested": species_model.requested_model,
                    "resolved_path": str(species_model.classifier_path),
                    "content_digest": species_model.classifier_digest,
                    "model_version": species_model.model_version,
                    "inference_device": species_model.inference_device,
                },
            }
        )

    domestic_taxon_ids = set(settings.detection.domestic_taxon_ids)
    for image, source_path in zip(candidates, source_paths, strict=True):
        inference_result = inference_by_path[source_path]
        speciesnet_classifications = {
            index: SpeciesNetClassification(
                label=(
                    "domestic"
                    if species_result.final_taxon_id in domestic_taxon_ids
                    else species_result.final_label
                ),
                confidence=species_result.final_taxon_confidence,
            )
            for index, _ in enumerate(inference_result.detections)
            if (species_result := species_results.get((source_path, index))) is not None
            and species_result.final_taxon_confidence is not None
        }
        decision = classify_detections(inference_result.detections, speciesnet_classifications)
        destination = get_detection_path(managed_session.session_path, decision.label) / source_path.name
        target_digest = image.content_digest
        target_size = image.content_size_bytes
        object_detections = [
            _to_object_detection(image.id, index, detection, species_results.get((source_path, index)))
            for index, detection in enumerate(inference_result.detections)
        ]
        analysis_results.append(
            ImageDetectionResult(
                image_id=image.id,
                predicted_label=decision.label,
                predicted_confidence=decision.confidence,
                decision_source=decision.source,
                megadetector_model=str(resolved_model.resolved_path),
                speciesnet_model=str(input_data.speciesnet_model),
                speciesnet_model_version=species_model.model_version if species_model else None,
                latitude=monitoring_site.latitude,
                longitude=monitoring_site.longitude,
                detections=object_detections,
            )
        )
        details = canonical_process_parameters(
            {
                "schema_version": 2,
                "label": decision.label,
                "confidence": decision.confidence,
                "decision_source": decision.source,
                "source": {
                    "content_digest": image.content_digest,
                    "size_bytes": image.content_size_bytes,
                },
                "target": {
                    "content_digest": target_digest,
                    "size_bytes": target_size,
                },
            }
        )
        plans.append(
            SessionProcessImagePlan(
                session_id=managed_session.session.id,
                process_name=PROCESS_NAME,
                image_id=image.id,
                decision="move",
                target_relative_path=_relative_path(managed_session.session_path, destination),
                planned_at=planned_at,
                decision_details_json=details,
            )
        )
        result.files_evaluated += 1
        _increment_label(result, decision.label)
    return plans, analysis_results, result, execution_details


def _to_object_detection(image_id: str, index: int, detection, species_result) -> ImageObjectDetection:
    predictions = []
    if species_result is not None:
        predictions = [
            ImageTaxonPrediction(
                rank=prediction.rank,
                taxon_id=prediction.taxon_id,
                taxon_class=prediction.taxon_class,
                taxon_order=prediction.taxon_order,
                taxon_family=prediction.taxon_family,
                taxon_genus=prediction.taxon_genus,
                taxon_species=prediction.taxon_species,
                common_name=prediction.common_name,
                confidence=prediction.confidence,
            )
            for prediction in species_result.predictions
        ]
    return ImageObjectDetection(
        id=f"{image_id}:{index}",
        image_id=image_id,
        category=detection.label,
        confidence=detection.confidence,
        bbox_x=detection.bbox_x,
        bbox_y=detection.bbox_y,
        bbox_width=detection.bbox_width,
        bbox_height=detection.bbox_height,
        final_taxon_id=species_result.final_taxon_id if species_result else None,
        final_taxon_rank=species_result.final_taxon_rank if species_result else None,
        final_taxon_confidence=species_result.final_taxon_confidence if species_result else None,
        predictions=predictions,
    )


def _validate_inference_result(result: MlImageResult, source_path: Path) -> None:
    if result.file_path != source_path:
        raise SessionProcessError(
            f"MegaDetector returned an unexpected image path: {result.file_path}"
        )


def _start_and_persist_plan(
    managed_session: ManagedSession,
    input_data: SessionDetectContentInput,
    parameters_json: str,
    execution_details: str,
    plans: list[SessionProcessImagePlan],
    analysis_results: list[ImageDetectionResult],
) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        processes = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            processes, managed_session.session.id, PROCESS_NAME, input_data.recover
        )
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        processes.start(managed_session.session.id, PROCESS_NAME, utc_now(), parameters_json)
        processes.set_execution_details(
            managed_session.session.id, PROCESS_NAME, execution_details
        )
        SessionProcessImagePlanRepository(sql_session).create_many(plans)
        ImageDetectionResultRepository(sql_session).replace_many(analysis_results)


def _load_existing_plans(
    managed_session: ManagedSession,
    input_data: SessionDetectContentInput,
    parameters_json: str,
) -> tuple[SessionProcess | None, list[SessionProcessImagePlan]]:
    with sql_session_scope(managed_session.database_path) as sql_session:
        processes = SessionProcessRepository(sql_session)
        existing = validate_process_attempt(
            processes, managed_session.session.id, PROCESS_NAME, input_data.recover
        )
        plans = SessionProcessImagePlanRepository(sql_session).list_for_process(
            managed_session.session.id, PROCESS_NAME
        )
        if existing is not None and input_data.recover and plans:
            return existing, plans
        validate_process_parameters(existing, parameters_json, PROCESS_NAME)
        return existing, plans


def _plan_details(plan: SessionProcessImagePlan) -> dict[str, object]:
    if plan.decision_details_json is None:
        raise SessionProcessError(f"Detection plan lacks details for {plan.image_id}")
    try:
        details = json.loads(plan.decision_details_json)
    except json.JSONDecodeError as exc:
        raise SessionProcessError(f"Detection plan details are invalid for {plan.image_id}") from exc
    if not isinstance(details, dict):
        raise SessionProcessError(f"Detection plan details are invalid for {plan.image_id}")
    return details


def _apply_plans(
    managed_session: ManagedSession,
    plans: list[SessionProcessImagePlan],
    result: _DetectContentSummary,
) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        images = {
            image.id: image
            for image in SessionImageRepository(sql_session).list_for_session(
                managed_session.session.id
            )
        }
    for plan in plans:
        image = images.get(plan.image_id)
        if image is None or plan.target_relative_path is None:
            raise SessionProcessError(f"Detection plan is invalid for {plan.image_id}")
        details = _plan_details(plan)
        label = str(details["label"])
        description = details.get("image_description")
        target = details["target"]
        source = details["source"]
        if not isinstance(target, dict) or not isinstance(source, dict):
            raise SessionProcessError(f"Detection plan is invalid for {plan.image_id}")
        target_digest = str(target["content_digest"])
        target_size = int(target["size_bytes"])
        source_digest = str(source["content_digest"])
        source_size = int(source["size_bytes"])
        destination = _resolve_session_path(managed_session.session_path, plan.target_relative_path)
        source_path = _resolve_session_path(managed_session.session_path, image.current_relative_path)
        state = f"detection/{label}"

        if image.current_relative_path == plan.target_relative_path:
            _require_content(destination, target_digest, target_size)
            result.files_moved += 1
            continue
        if source_path.exists():
            _require_content(source_path, source_digest, source_size)
            replaced = destination.exists() and not _content_matches(destination, target_digest, target_size)
            if destination.exists() and _content_matches(destination, target_digest, target_size):
                source_path.unlink()
            else:
                move_file_with_staged_copy(
                    source_path,
                    destination,
                    transform=(
                        lambda staged_path: _write_legacy_description(staged_path, str(description))
                        if description is not None
                        else None
                    ),
                    verify=lambda staged_path: _content_matches(
                        staged_path, target_digest, target_size
                    ),
                )
            with sql_session_scope(managed_session.database_path) as sql_session:
                SessionImageRepository(sql_session).relocate_with_content(
                    image.id, plan.target_relative_path, state, target_digest, target_size
                )
            result.files_moved += 1
            if replaced:
                result.files_replaced += 1
            continue
        if not destination.exists() or not _content_matches(destination, target_digest, target_size):
            raise SessionProcessError(f"Detection plan target is inconsistent for {image.id}")
        with sql_session_scope(managed_session.database_path) as sql_session:
            SessionImageRepository(sql_session).relocate_with_content(
                image.id, plan.target_relative_path, state, target_digest, target_size
            )
        result.files_moved += 1


def _content_matches(path: Path, digest: str, size: int) -> bool:
    return path.is_file() and path.stat().st_size == size and get_content_digest(path) == digest


def _write_legacy_description(path: Path, description: str) -> None:
    """Apply EXIF only while replaying a persisted V1 detection plan."""
    from wv.core.exif import write_exif_image_description

    write_exif_image_description(path, description)


def _complete(
    managed_session: ManagedSession, result: _DetectContentSummary
) -> SessionProcess:
    with sql_session_scope(managed_session.database_path) as sql_session:
        return SessionProcessRepository(sql_session).complete(
            managed_session.session.id,
            PROCESS_NAME,
            status="completed_with_failures" if result.files_failed else "completed",
            completed_at=utc_now(),
            files_discovered=result.files_discovered,
            files_processed=result.files_evaluated,
            files_selected=result.files_evaluated,
            files_moved=result.files_moved,
            files_ignored=result.files_ignored,
            files_failed=result.files_failed,
        )


def _fail(managed_session: ManagedSession, error: Exception, result: _DetectContentSummary) -> None:
    with sql_session_scope(managed_session.database_path) as sql_session:
        SessionProcessRepository(sql_session).fail(
            managed_session.session.id,
            PROCESS_NAME,
            completed_at=utc_now(),
            failure_message=str(error),
            files_discovered=result.files_discovered,
            files_processed=result.files_evaluated,
            files_selected=0,
            files_moved=result.files_moved,
            files_ignored=result.files_ignored,
            files_failed=result.files_failed + 1,
        )


def _result(
    managed_session: ManagedSession,
    process: SessionProcess | None,
    summary: _DetectContentSummary,
) -> SessionDetectContentResult:
    return SessionDetectContentResult(
        session_id=managed_session.session.id,
        process=process,
        files_discovered=summary.files_discovered,
        files_evaluated=summary.files_evaluated,
        files_moved=summary.files_moved,
        files_ignored=summary.files_ignored,
        files_failed=summary.files_failed,
        files_replaced=summary.files_replaced,
        files_animal=summary.files_animal,
        files_human=summary.files_human,
        files_vehicle=summary.files_vehicle,
        files_domestic=summary.files_domestic,
        files_empty=summary.files_empty,
        files_other=summary.files_other,
        destination=summary.destination,
        dry_run=summary.dry_run,
    )


def run(input_data: SessionDetectContentInput) -> SessionDetectContentResult:
    """Run plan-backed MegaDetector content classification for a session."""
    managed_session = resolve_managed_session(input_data.session_id)
    input_data = _resolve_input(managed_session, input_data)
    validate_detection_settings(
        int(input_data.batch_size), load_processing_config().detection.domestic_taxon_ids
    )
    parameters_json = _parameters_json(input_data)
    with _exclusive_session_lock(managed_session.session_path, input_data.dry_run):
        existing, plans = _load_existing_plans(managed_session, input_data, parameters_json)
        if existing is not None and plans:
            if existing.parameters_json is None:
                raise SessionProcessError("Detection process has no recorded parameters.")
            parameters_json = existing.parameters_json
        analysis_results: list[ImageDetectionResult] = []
        if plans:
            ignored = sum(
                1
                for path in managed_session.init_path.iterdir()
                if not path.is_file() or not is_allowed_image_file(path)
            )
            result = _DetectContentSummary(
                files_discovered=len(plans) + ignored,
                files_evaluated=len(plans),
                files_ignored=ignored,
                destination=get_detection_path(managed_session.session_path),
                dry_run=input_data.dry_run,
            )
            for plan in plans:
                _increment_label(result, str(_plan_details(plan)["label"]))
        else:
            candidates, discovered, ignored = _load_candidates(managed_session)
            result = _DetectContentSummary(
                files_discovered=discovered,
                files_ignored=ignored,
                destination=get_detection_path(managed_session.session_path),
                dry_run=input_data.dry_run,
            )
            try:
                plans, analysis_results, planned_result, execution_details = _build_plan(
                    managed_session, input_data, candidates
                )
                planned_result.files_discovered = discovered
                planned_result.files_ignored = ignored
                planned_result.destination = get_detection_path(managed_session.session_path)
                planned_result.dry_run = input_data.dry_run
                result = planned_result
            except Exception as exc:
                if not input_data.dry_run:
                    with sql_session_scope(managed_session.database_path) as sql_session:
                        processes = SessionProcessRepository(sql_session)
                        processes.start(managed_session.session.id, PROCESS_NAME, utc_now(), parameters_json)
                    _fail(managed_session, exc, result)
                raise

        if input_data.dry_run:
            return _result(managed_session, None, result)
        if not existing or not plans:
            _start_and_persist_plan(
                managed_session, input_data, parameters_json, execution_details, plans, analysis_results
            )
        else:
            with sql_session_scope(managed_session.database_path) as sql_session:
                SessionProcessRepository(sql_session).start(
                    managed_session.session.id, PROCESS_NAME, utc_now(), parameters_json
                )
        try:
            _apply_plans(managed_session, plans, result)
            process = _complete(managed_session, result)
        except Exception as exc:
            _fail(managed_session, exc, result)
            raise
    return _result(managed_session, process, result)
