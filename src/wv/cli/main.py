import typer

from wv.cli.commands import clean, detect, ingest, pipeline

app = typer.Typer(
    name="wildlife-vision",
    help="An offline-first set of automated image pipelines for managing, organizing, reviewing, and curating images captured by trail and hunting cameras.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


app.add_typer(clean, name="clean")
app.add_typer(detect, name="detect")
app.add_typer(ingest, name="ingest")
app.add_typer(pipeline, name="pipeline")


def main():
    app()


if __name__ == "__main__":
    main()
