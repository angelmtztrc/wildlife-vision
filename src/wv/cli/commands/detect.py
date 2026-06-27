import typer

app = typer.Typer(help="Run content detection on photos.")


@app.command("content")
def detect_content():
    return None
