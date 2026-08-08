from pathlib import Path

from wv.cli.main import app


def test_monitoring_site_cli_requires_geography_and_area(
    cli_runner, configured_workspace: Path
):
    area = cli_runner.invoke(app, ["monitoring-area", "create", "AREA002", "--name", "South Ranch"])
    created = cli_runner.invoke(
        app,
        [
            "monitoring-site", "create", "SITE003", "--area", "AREA002",
            "--name", "Fence Trail", "--latitude", "28.57", "--longitude", "-101.16",
        ],
    )
    listed = cli_runner.invoke(app, ["monitoring-site", "list", "--area", "AREA002"])
    shown = cli_runner.invoke(app, ["monitoring-site", "show", "SITE003"])

    assert area.exit_code == 0
    assert created.exit_code == 0
    assert listed.output.strip() == "SITE003\tAREA002\tFence Trail"
    assert "area: AREA002" in shown.output
    assert "latitude: 28.57" in shown.output


def test_monitoring_site_cli_rejects_missing_coordinates(
    cli_runner, configured_workspace: Path
):
    result = cli_runner.invoke(
        app, ["monitoring-site", "create", "SITE003", "--area", "AREA001", "--name", "Missing"]
    )

    assert result.exit_code == 2
    assert "Missing option" in result.output
