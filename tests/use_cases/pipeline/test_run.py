from types import SimpleNamespace
from contextlib import nullcontext

import pytest

import wv.use_cases.pipeline.run as pipeline
from wv.domain.session import IngestSession
from wv.use_cases.pipeline.run import PipelineRunError, PipelineRunInput, run
from wv.use_cases.session.status import SessionStageStatus, SessionStatusResult


SESSION = IngestSession(
    id="20260808_120000__SITE001",
    monitoring_site_id="SITE001",
    source_path="/Volumes/SD",
    mode="copy",
    recursive=False,
    started_at="2026-08-08T12:00:00+00:00",
    ingest_status="completed",
)


@pytest.fixture(autouse=True)
def bypass_workflow_lock(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "resolve_managed_session",
        lambda session_id: SimpleNamespace(session_path=SESSION.id),
    )
    monkeypatch.setattr(pipeline, "session_workflow_lock", lambda session_path: nullcontext())
    monkeypatch.setattr(
        pipeline,
        "load_processing_config",
        lambda: SimpleNamespace(
            overexposed_ir=SimpleNamespace(
                mean_threshold=200.0,
                std_threshold=25.0,
                high_level=220,
                pct_high_threshold=0.6,
            ),
            bursts=SimpleNamespace(burst_gap_threshold=60, similarity_threshold=5),
            detection=SimpleNamespace(
                model="MDV5A",
                speciesnet_model="speciesnet",
                batch_size=4,
            ),
        ),
    )


def _status(overall: str, process: str | None, action: str | None, stages=None):
    return SessionStatusResult(
        session=SESSION,
        monitoring_area_id="AREA001",
        overall_status=overall,
        next_process=process,
        next_action=action,
        stages=stages
        or [SessionStageStatus(name=name) for name in pipeline.PROCESS_NAMES],
    )


def test_run_executes_all_stages_in_order(monkeypatch):
    statuses = iter(
        [
            _status("ready", "clean_corrupted", "run"),
            _status("processing", "clean_overexposed_ir", "run"),
            _status("processing", "detect_content", "run"),
            _status("completed", None, None),
        ]
    )
    calls: list[str] = []
    monkeypatch.setattr(pipeline, "run_session_status", lambda input_data: next(statuses))
    for name in ("run_clean_corrupted", "run_clean_overexposed_ir", "run_detect_content"):
        monkeypatch.setattr(
            pipeline,
            name,
            lambda input_data, name=name: (calls.append(name), SimpleNamespace(process=SimpleNamespace(status="completed"), files_failed=0))[1],
        )

    result = run(PipelineRunInput(session_id=SESSION.id))

    assert calls == [
        "run_clean_corrupted",
        "run_clean_overexposed_ir",
        "run_detect_content",
    ]
    assert result.final_status == "completed"


def test_run_stops_on_partial_failure(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "run_session_status",
        lambda input_data: _status("ready", "clean_corrupted", "run"),
    )
    monkeypatch.setattr(
        pipeline,
        "run_clean_corrupted",
        lambda input_data: SimpleNamespace(process=SimpleNamespace(status="completed_with_failures"), files_failed=1),
    )

    result = run(PipelineRunInput(session_id=SESSION.id))

    assert result.final_status == "completed_with_failures"
    assert result.stopped_at == "clean_corrupted"


def test_run_honors_next_and_inclusive_until(monkeypatch):
    first = _status("ready", "clean_corrupted", "run")
    monkeypatch.setattr(pipeline, "run_session_status", lambda input_data: first)
    monkeypatch.setattr(
        pipeline,
        "run_clean_corrupted",
        lambda input_data: SimpleNamespace(process=SimpleNamespace(status="completed"), files_failed=0),
    )

    next_result = run(PipelineRunInput(session_id=SESSION.id, next_only=True))
    until_result = run(PipelineRunInput(session_id=SESSION.id, until="corrupted"))

    assert next_result.stopped_at == "clean_corrupted"
    assert until_result.stopped_at == "clean_corrupted"


def test_until_completed_stage_is_a_stopped_noop(monkeypatch):
    stages = [SessionStageStatus(name=name) for name in pipeline.PROCESS_NAMES]
    stages[0] = SessionStageStatus(name="clean_corrupted", status="completed")
    monkeypatch.setattr(
        pipeline,
        "run_session_status",
        lambda input_data: _status("processing", "clean_overexposed_ir", "run", stages),
    )

    result = run(PipelineRunInput(session_id=SESSION.id, until="corrupted"))

    assert result.stages == []
    assert result.final_status == "stopped"
    assert result.stopped_at == "clean_corrupted"


def test_until_final_stage_reports_completed(monkeypatch):
    statuses = iter(
        [
            _status("processing", "detect_content", "run"),
            _status("completed", None, None),
        ]
    )
    monkeypatch.setattr(pipeline, "run_session_status", lambda input_data: next(statuses))
    monkeypatch.setattr(
        pipeline,
        "run_detect_content",
        lambda input_data: SimpleNamespace(process=SimpleNamespace(status="completed"), files_failed=0),
    )

    result = run(PipelineRunInput(session_id=SESSION.id, until="detect-content"))

    assert result.final_status == "completed"
    assert result.stopped_at == "detect_content"


def test_run_requires_explicit_recovery(monkeypatch):
    stages = [SessionStageStatus(name=name) for name in pipeline.PROCESS_NAMES]
    stages[0] = SessionStageStatus(name="clean_corrupted", status="in_progress")
    monkeypatch.setattr(
        pipeline,
        "run_session_status",
        lambda input_data: _status("process_in_progress", "clean_corrupted", "recover", stages),
    )

    with pytest.raises(PipelineRunError, match="Use --recover"):
        run(PipelineRunInput(session_id=SESSION.id))


def test_run_rejects_combined_stage_controls():
    with pytest.raises(PipelineRunError, match="cannot be used together"):
        run(PipelineRunInput(session_id=SESSION.id, next_only=True, until="detect-content"))


def test_retry_uses_recorded_parameters(monkeypatch):
    stages = [SessionStageStatus(name=name) for name in pipeline.PROCESS_NAMES]
    stages[1] = SessionStageStatus(
        name="clean_overexposed_ir",
        status="failed",
        parameters_json='{"high_level":221,"mean_threshold":201.0,"pct_high_threshold":0.7,"std_threshold":20.0}',
    )
    monkeypatch.setattr(
        pipeline,
        "run_session_status",
        lambda input_data: _status("processing_failed", "clean_overexposed_ir", "retry", stages),
    )
    received = None

    def fake_run(input_data):
        nonlocal received
        received = input_data
        return SimpleNamespace(process=SimpleNamespace(status="completed"), files_failed=0)

    monkeypatch.setattr(pipeline, "run_clean_overexposed_ir", fake_run)

    result = run(PipelineRunInput(session_id=SESSION.id, next_only=True))

    assert result.stopped_at == "clean_overexposed_ir"
    assert received.mean_threshold == 201.0
    assert received.high_level == 221
