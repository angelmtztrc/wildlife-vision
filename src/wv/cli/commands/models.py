from typing import Annotated

import typer

from wv.cli.table import print_table
from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.use_cases.models.list import ModelListInput
from wv.use_cases.models.list import run as run_list
from wv.use_cases.models.setup import ModelSetupInput
from wv.use_cases.models.setup import run as run_setup
from wv.use_cases.models.status import ModelStatusInput
from wv.use_cases.models.status import run as run_status
from wv.workspace.common import WorkspaceError

app = typer.Typer(help="Prepare and inspect models selected by the active workspace.")
logger = get_logger(__name__)


@app.command("list")
def list_models():
    """List supported MegaDetector and SpeciesNet model aliases."""
    result = run_list(ModelListInput())
    print_table(
        ["ENGINE", "ALIAS", "MODEL", "DESCRIPTION"],
        ((item.engine, item.alias, item.model, item.description) for item in result.items),
        ratios=[2, 1, 3, 4],
    )


@app.command("setup")
def setup_models(
    megadetector: Annotated[
        str | None,
        typer.Option("--megadetector", help="MegaDetector alias, canonical model name, or local model path."),
    ] = None,
    speciesnet: Annotated[
        str | None,
        typer.Option("--speciesnet", help="SpeciesNet crop-model alias, provider ID, or local model directory."),
    ] = None,
    repair: Annotated[
        bool,
        typer.Option("--repair", help="Recreate the SpeciesNet runtime and re-download MegaDetector."),
    ] = False,
):
    """Prepare selected models and activate them for the active workspace."""
    try:
        result = run_setup(
            ModelSetupInput(
                megadetector=megadetector,
                speciesnet=speciesnet,
                repair=repair,
            )
        )
    except (WorkspaceError, ValueError, RuntimeError) as exc:
        logger.error("Model setup failed: %s", exc)
        raise typer.Exit(code=1) from exc

    logger.done(
        "Models ready: megadetector=%s path=%s device=%s speciesnet=%s path=%s version=%s device=%s domestic_taxa=%s",
        result.megadetector_model,
        display_path(result.megadetector_path),
        result.megadetector_device,
        result.speciesnet_model,
        display_path(result.speciesnet_path),
        result.speciesnet_version,
        result.speciesnet_device,
        result.domestic_taxa_count,
    )


@app.command("status")
def status_models():
    """Show readiness for models selected by the active workspace."""
    try:
        result = run_status(ModelStatusInput())
    except WorkspaceError as exc:
        logger.error("Model status failed: %s", exc)
        raise typer.Exit(code=1) from exc
    print_table(
        ["ENGINE", "SELECTED", "DEVICE", "STATUS"],
        ((item.engine, item.selected, item.device, item.status) for item in result.items),
        ratios=[2, 4, 1, 1],
    )
    logger.done("Configured domestic taxa: %s", result.domestic_taxa_count)
