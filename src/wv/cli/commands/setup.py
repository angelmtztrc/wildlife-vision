from typing import Annotated

import typer

from wv.cli.presentation import render_command_summary
from wv.cli.runtime import get_logger, get_runtime
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
    runtime = get_runtime()
    logger = get_logger(__name__)
    logger.info(
        "Starting setup. Model: %s. Force download: %s.",
        model,
        "yes" if force_download else "no",
    )

    try:
        result = run_setup(
            SetupInput(
                model=model,
                force_download=force_download,
            )
        )
    except Exception as exc:
        logger.error("Setup failed: %s", exc)
        render_command_summary(
            runtime,
            title="Setup Summary",
            message="Setup failed.",
            rows=[
                ("Model", model),
                ("Ready", "no"),
                ("Error", exc),
            ],
            level_name="ERROR",
        )
        raise typer.Exit(code=1) from exc

    render_command_summary(
        runtime,
        title="Setup Summary",
        message="Setup finished.",
        rows=[
            ("Model", result.model),
            ("Resolved model", result.resolved_model),
            ("Ready", "yes" if result.ready else "no"),
            ("Inference device", result.inference_device),
        ],
    )

    return None
