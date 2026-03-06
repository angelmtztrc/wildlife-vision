import typer

from wv.cli.commands import detect, organise, gui

app = typer.Typer(
    name="wildlife-vision",
    help="Offline-first automated image pipelines for wildlife trail camera photos.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(organise.app, name="organise")
app.add_typer(detect.app, name="detect")
app.add_typer(gui.app, name="gui")


@app.command()
def version():
    from wv import __version__

    typer.echo(f"wildlife-vision {__version__}")


if __name__ == "__main__":
    app()
