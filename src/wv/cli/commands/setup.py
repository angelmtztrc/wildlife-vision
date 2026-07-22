from typing import Annotated

import typer

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.setup import DEFAULT_MODEL, SetupInput
from wv.use_cases.setup import run as run_setup

logger = get_logger(__name__)


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
    """Prepare the MegaDetector model for local CLI commands that require inference."""
    logger.info(
        "Starting setup (model=%s, force_download=%s)",
        model,
        force_download,
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
        raise typer.Exit(code=1) from exc

    logger.done(
        "Finished setup: model=%s resolved_model=%s ready=%s inference_device=%s",
        result.model,
        display_path(result.resolved_model),
        result.ready,
        result.inference_device,
    )

    return None
