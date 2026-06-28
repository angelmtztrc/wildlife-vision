from typing import Annotated

import typer

from wv.use_cases.setup import DEFAULT_MODEL, SetupInput
from wv.use_cases.setup import run as run_setup


def setup(
    model: Annotated[str, typer.Option(help="MegaDetector model name or path.")] = DEFAULT_MODEL,
    force_download: Annotated[
        bool,
        typer.Option(
            "--force-download",
            help="Re-download the model even if it already exists locally.",
        ),
    ] = False,
):
    try:
        result = run_setup(
            SetupInput(
                model=model,
                force_download=force_download,
            )
        )
    except Exception as exc:
        typer.echo(f"Model: {model}")
        typer.echo("Ready: no")
        typer.echo(f"Error: {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"Model: {result.model}")
    typer.echo(f"Resolved model: {result.resolved_model}")
    typer.echo(f"Ready: {'yes' if result.ready else 'no'}")
    typer.echo(f"Inference device: {result.inference_device}")

    return None
