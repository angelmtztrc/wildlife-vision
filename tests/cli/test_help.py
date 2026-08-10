import pytest
from typer.main import get_command

from wv.cli.main import app


def _get_command(path: list[str]):
    command = get_command(app)
    for name in path:
        command = command.commands[name]
    return command


def _walk_commands(command):
    yield command
    for child in getattr(command, "commands", {}).values():
        yield from _walk_commands(child)


def test_all_commands_and_parameters_have_help():
    for command in _walk_commands(_get_command([])):
        assert command.help
        for parameter in command.params:
            assert parameter.help


@pytest.mark.parametrize(
    ("command", "summary"),
    [
        ([], "Offline-first tools for ingesting, processing, reviewing, and exporting trail-camera images."),
        (["models"], "Prepare and inspect models selected by the active workspace."),
        (["models", "list"], "List supported MegaDetector and SpeciesNet model aliases."),
        (["models", "setup"], "Prepare selected models and activate them for the active workspace."),
        (["models", "status"], "Show readiness for models selected by the active workspace."),
        (["clean", "corrupted"], "Move unreadable JPEG files directly in SOURCE to ignored/corrupted."),
        (["clean", "overexposed-ir"], "Move likely overexposed IR JPEG files directly in SOURCE to ignored/overexposed."),
        (["clean", "bursts"], "Keep selected JPEGs from similar bursts and move the rest to ignored/bursts."),
        (["config", "init"], "Create the default config when the active workspace has no config file."),
        (["config", "list"], "List known keys and values from the active workspace config."),
        (["config", "get"], "Print one value from the active workspace config."),
        (["config", "set"], "Set and validate one value in the active workspace config."),
        (["config", "reset"], "Reset one active workspace setting to its built-in default."),
        (["config", "validate"], "Validate the active workspace config and processing settings."),
        (["config", "path"], "Print the active workspace config path."),
        (["device", "create"], "Create a device record in the active workspace."),
        (["device", "list"], "List device records in the active workspace."),
        (["device", "show"], "Show one device record."),
        (["device", "update"], "Update one or more fields on a device record."),
        (["export", "favorites"], "Copy favorited animal detections from a completed managed session."),
        (["gui", "review-detection"], "Review and relabel images in one completed detection bucket."),
        (["gui", "favorites"], "Review favorite status for animal detections."),
        (["ingest", "sd"], "Ingest JPEGs from an initialized SD card into the active workspace."),
        (["ingest", "folder"], "Ingest JPEGs from a folder into a managed session in the active workspace."),
        (["monitoring-area", "create"], "Create a monitoring area in the active workspace."),
        (["monitoring-area", "list"], "List monitoring areas in the active workspace."),
        (["monitoring-area", "show"], "Show one monitoring area."),
        (["monitoring-area", "update"], "Update one or more fields on a monitoring area."),
        (["monitoring-site", "create"], "Create a monitoring site in the active workspace."),
        (["monitoring-site", "list"], "List monitoring sites in the active workspace."),
        (["monitoring-site", "show"], "Show one monitoring site."),
        (["monitoring-site", "update"], "Update one or more fields on a monitoring site."),
        (["pipeline", "run"], "Run eligible stages in order: corrupted, overexposed IR, then content detection."),
        (["sd", "init"], "Write monitoring-site metadata to an uninitialized SD card."),
        (["sd", "show"], "Show monitoring-site metadata stored on an initialized SD card."),
        (["sd", "update"], "Change the monitoring site stored on an initialized SD card."),
        (["sd", "clear"], "Remove the SD card's Wildlife Vision config file without deleting images."),
        (["session", "list"], "List incomplete sessions first, then completed sessions by recency."),
        (["session", "status"], "Show ingest, processing, inventory, and filesystem status for a session."),
        (["session", "clean", "corrupted"], "Run the first managed stage and move unreadable images to ignored/corrupted."),
        (["session", "clean", "overexposed-ir"], "Run the second managed stage and move likely overexposed IR images."),
        (["session", "clean", "bursts"], "Run the third managed stage and reduce similar image bursts."),
        (["session", "detect", "content"], "Classify managed images as animal, human, vehicle, domestic, empty, or other."),
        (["workspace", "init"], "Initialize and activate an existing directory as a workspace."),
        (["workspace", "activate"], "Make an existing initialized workspace active."),
        (["workspace", "migrate"], "Upgrade the active workspace config and database to current versions."),
        (["workspace", "show"], "Show the configured workspace path and required component status."),
        (["workspace", "validate"], "Validate the active workspace structure, config, and database revision."),
    ],
)
def test_command_help_includes_summary(command: list[str], summary: str):
    assert _get_command(command).help == summary


@pytest.mark.parametrize(
    ("command", "text"),
    [
        (["clean", "corrupted"], "immediate .jpg and .jpeg files are scanned; subdirectories are not searched."),
        (["ingest", "sd"], ".wv/config.yml monitoring-site metadata."),
        (["ingest", "folder"], "drain copies and verifies each JPEG before deleting its source; copy retains sources."),
        (["sd", "clear"], ".wv/config.yml file will be removed."),
        (["pipeline", "run"], "retries use the recorded value."),
        (["session", "detect", "content"], "a new plan still runs inference."),
        (["gui", "review-detection"], "animal, human, vehicle, domestic, empty, or other."),
        (["config", "set"], "YAML value to assign to the config key."),
        (["workspace", "activate"], "Existing initialized workspace directory to activate."),
    ],
)
def test_command_help_includes_important_parameter_guidance(command: list[str], text: str):
    assert text in " ".join(parameter.help or "" for parameter in _get_command(command).params)
