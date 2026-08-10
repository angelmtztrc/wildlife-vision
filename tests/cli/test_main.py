from typer.main import get_command

from wv.cli.main import app


def test_main_help_lists_top_level_commands(cli_runner):
    result = cli_runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert get_command(app).help == "Offline-first tools for ingesting, processing, reviewing, and exporting trail-camera images."
    assert "--verbose" in result.output
    assert "clean" in result.output
    assert "config" in result.output
    assert "detect" not in result.output
    assert "device" in result.output
    assert "export" in result.output
    assert "gui" in result.output
    assert "ingest" in result.output
    assert "models" in result.output
    assert "monitoring-site" in result.output
    assert "monitoring-area" in result.output
    assert "pipeline" in result.output
    assert "sd" in result.output
    assert "session" in result.output
    assert "setup" not in result.output
    assert "workspace" in result.output
