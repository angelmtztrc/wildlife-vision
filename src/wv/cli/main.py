import typer

from wv.cli.commands import clean, detect, ingest, pipeline, setup
from wv.core.logger import configure_external_output, set_verbose

app = typer.Typer(
    name="wildlife-vision",
    help="An offline-first set of automated image pipelines for managing, organizing, reviewing, and curating images captured by trail and hunting cameras.",
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
app.add_typer(detect.app, name="detect")
app.add_typer(ingest.app, name="ingest")
app.add_typer(pipeline.app, name="pipeline")
app.command(
    "setup",
    help="Prepare MegaDetector for local inference by resolving or downloading the configured model.",
)(setup.setup)


def main():
    app()


if __name__ == "__main__":
    main()
