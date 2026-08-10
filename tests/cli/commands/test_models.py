from pathlib import Path

from wv.cli.main import app
from wv.use_cases.models.list import ModelListItem, ModelListResult
from wv.use_cases.models.status import ModelStatusItem, ModelStatusResult


def test_models_list_prints_supported_aliases(cli_runner, monkeypatch):
    monkeypatch.setattr(
        "wv.cli.commands.models.run_list",
        lambda input_data: ModelListResult(
            [ModelListItem("MegaDetector", "v5a", "MDV5A", "Detector")]
        ),
    )

    result = cli_runner.invoke(app, ["models", "list"])

    assert result.exit_code == 0
    assert "v5a" in result.output


def test_models_status_reports_unprepared_models(cli_runner, monkeypatch):
    monkeypatch.setattr(
        "wv.cli.commands.models.run_status",
        lambda input_data: ModelStatusResult(
            [ModelStatusItem("MegaDetector", "MDV5A", "-", "not ready")],
            domestic_taxa_count=1,
            ready=False,
        ),
    )

    result = cli_runner.invoke(app, ["models", "status"])

    assert result.exit_code == 0
    assert "not ready" in result.output
