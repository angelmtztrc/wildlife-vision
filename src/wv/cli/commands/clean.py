import typer

app = typer.Typer(
    help="Identify and clean corrupted, overexposed IR, and burst photos."
)


@app.command("corrupted")
def clean_corrupted():
    return None


@app.command("overexposed-ir")
def clean_overexposed_ir():
    return None


@app.command("bursts")
def clean_bursts():
    return None
