from pathlib import Path

from wv.cli.main import app


def test_monitoring_area_list_renders_table(cli_runner, configured_workspace: Path):
    cli_runner.invoke(app, ["monitoring-area", "create", "--id", "AREA002", "--name", "South Ranch"])

    result = cli_runner.invoke(app, ["monitoring-area", "list"])

    assert result.exit_code == 0
    assert "AREA ID" in result.output
    assert "NAME" in result.output
    assert "AREA001" in result.output
    assert "AREA002" in result.output
    assert "South Ranch" in result.output
    assert result.output.index("AREA001") < result.output.index("AREA002")
