import typer

from wv.cli.commands import clean, config, device, export, gui, ingest, models, monitoring_area, monitoring_site, pipeline, sd, session, workspace
from wv.core.logger import configure_external_output, set_verbose

app = typer.Typer(
    name="wildlife-vision",
    help="Offline-first tools for ingesting, processing, reviewing, and exporting trail-camera images.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable DEBUG logging output.",
    ),
):
    set_verbose(verbose)
    configure_external_output(verbose)
    return None


app.add_typer(clean.app, name="clean")
app.add_typer(config.app, name="config")
app.add_typer(device.app, name="device")
app.add_typer(export.app, name="export")
app.add_typer(gui.app, name="gui")
app.add_typer(ingest.app, name="ingest")
app.add_typer(models.app, name="models")
app.add_typer(monitoring_site.app, name="monitoring-site")
app.add_typer(monitoring_area.app, name="monitoring-area")
app.add_typer(pipeline.app, name="pipeline")
app.add_typer(sd.app, name="sd")
app.add_typer(session.app, name="session")
app.add_typer(workspace.app, name="workspace")


def main():
    app()


if __name__ == "__main__":
    main()
