from wv.cli.main import app


def test_main_help_lists_top_level_commands(cli_runner):
    result = cli_runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--verbose" in result.output
    assert "clean" in result.output
    assert "detect" in result.output
    assert "ingest" in result.output
    assert "pipeline" in result.output
    assert "setup" in result.output
