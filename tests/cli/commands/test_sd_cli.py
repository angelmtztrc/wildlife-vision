from pathlib import Path

from wv.cli.main import app


def test_sd_cli_manages_monitoring_site_metadata(
    cli_runner, configured_workspace: Path, tmp_path: Path
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()

    initialized = cli_runner.invoke(
        app, ["sd", "init", str(sd_path), "--monitoring-site", "SITE001"]
    )
    shown = cli_runner.invoke(app, ["sd", "show", str(sd_path)])
    updated = cli_runner.invoke(
        app, ["sd", "update", str(sd_path), "--monitoring-site", "SITE002"]
    )
    cleared = cli_runner.invoke(app, ["sd", "clear", str(sd_path)])

    assert initialized.exit_code == 0
    assert "monitoring_site=SITE001" in initialized.output
    assert shown.exit_code == 0
    assert "monitoring_site_id: SITE001" in shown.output
    assert "device_id" not in shown.output
    assert updated.exit_code == 0
    assert cleared.exit_code == 0
    assert not (sd_path / ".wv" / "config.yml").exists()


def test_sd_cli_rejects_symlinked_card_path(
    cli_runner, configured_workspace: Path, tmp_path: Path
):
    sd_path = tmp_path / "sd-card"
    sd_path.mkdir()
    sd_link = tmp_path / "sd-link"
    sd_link.symlink_to(sd_path, target_is_directory=True)

    result = cli_runner.invoke(
        app, ["sd", "init", str(sd_link), "--monitoring-site", "SITE001"]
    )

    assert result.exit_code == 1
    assert "Symbolic links are not supported" in result.output
