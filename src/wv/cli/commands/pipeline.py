import typer

app = typer.Typer(help="Run image preprocessing pipeline steps.")


@app.command("preprocess")
def pipeline_preprocess():
    return None
