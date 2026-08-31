from wv.cli.main import app
from wv.use_cases.session.list import ListSessionsResult
from wv.use_cases.pipeline.run import PipelineRunResult, PipelineStageResult


def test_pipeline_run_forwards_options_and_prints_summary(cli_runner, monkeypatch):
    received = None

    def fake_run(input_data):
        nonlocal received
        received = input_data
        return PipelineRunResult(
            session_id=input_data.session_id,
            stages=[PipelineStageResult("clean_corrupted", "completed", 0)],
            final_status="stopped",
            stopped_at="clean_corrupted",
        )

    monkeypatch.setattr("wv.cli.commands.pipeline.run_pipeline", fake_run)

    result = cli_runner.invoke(
        app,
        ["pipeline", "run", "20260808_120000__SITE001", "--next", "--mean-threshold", "210"],
    )

    assert result.exit_code == 0
    assert received.next_only is True
    assert received.mean_threshold == 210.0
    assert "status=stopped" in result.output
    assert "stages=clean_corrupted" in result.output


def test_pipeline_run_returns_failure_for_stage_file_failures(cli_runner, monkeypatch):
    monkeypatch.setattr(
        "wv.cli.commands.pipeline.run_pipeline",
        lambda input_data: PipelineRunResult(
            session_id=input_data.session_id,
            stages=[PipelineStageResult("clean_corrupted", "completed_with_failures", 1)],
            final_status="completed_with_failures",
            stopped_at="clean_corrupted",
        ),
    )

    result = cli_runner.invoke(app, ["pipeline", "run", "20260808_120000__SITE001"])

    assert result.exit_code == 1
    assert "completed_with_failures" in result.output


def test_pipeline_session_completion_filters_persisted_ids(monkeypatch):
    class Session:
        def __init__(self, session_id: str):
            self.id = session_id

    monkeypatch.setattr(
        "wv.cli.completion.run_list_sessions",
        lambda input_data: ListSessionsResult(
            items=[Session("20260808_120000__SITE001"), Session("20260809_120000__SITE002")]
        ),
    )

    from wv.cli.completion import complete_session_id

    assert complete_session_id("20260808") == ["20260808_120000__SITE001"]
