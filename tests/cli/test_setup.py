from pathlib import Path

import pytest

import wv.cli.commands.setup as setup_command
from wv.cli.main import app
from wv.use_cases.setup import SetupResult


def test_setup_prints_summary_for_success(cli_runner, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        setup_command,
        "run_setup",
        lambda input_data: SetupResult(
            model=input_data.model,
            resolved_model=Path("/tmp/md_v5a.0.1.pt"),
            ready=True,
            inference_device="GPU",
        ),
    )

    result = cli_runner.invoke(app, ["setup"])

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "Starting setup" in result.output
    assert "[DONE]" in result.output
    assert "Finished setup" in result.output
    assert "model=MDV5A" in result.output
    assert "resolved_model=/tmp/md_v5a.0.1.pt" in result.output
    assert "ready=True" in result.output
    assert "inference_device=GPU" in result.output


def test_setup_exits_with_code_one_when_bootstrap_fails(
    cli_runner, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        setup_command,
        "run_setup",
        lambda input_data: (_ for _ in ()).throw(RuntimeError("download failed")),
    )

    result = cli_runner.invoke(app, ["setup"])

    assert result.exit_code == 1
    assert "[ERROR]" in result.output
    assert "download failed" in result.output
    assert "Setup failed" in result.output


def test_setup_verbose_uses_line_based_logs(cli_runner, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        setup_command,
        "run_setup",
        lambda input_data: SetupResult(
            model=input_data.model,
            resolved_model=Path("/tmp/md_v5a.0.1.pt"),
            ready=True,
            inference_device="GPU",
        ),
    )

    result = cli_runner.invoke(app, ["--verbose", "setup"])

    assert result.exit_code == 0
    assert "[INFO]" in result.output
    assert "[DONE]" in result.output
    assert "Finished setup" in result.output
