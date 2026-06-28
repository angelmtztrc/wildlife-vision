from pathlib import Path

import pytest

from wv.cli.commands import clean
from wv.use_cases.clean.bursts import CleanBurstsResult
from wv.use_cases.clean.corrupted import CleanCorruptedResult
from wv.use_cases.clean.overexposed_ir import CleanOverexposedIrResult


def test_clean_corrupted_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    monkeypatch.setattr(
        clean,
        "run_clean_corrupted",
        lambda input_data: CleanCorruptedResult(
            files_discovered=3,
            files_moved=1,
            files_ignored=1,
            files_corrupted=1,
            files_failed=0,
            destination=output / "ignored" / "corrupted",
            dry_run=True,
        ),
    )

    result = cli_runner.invoke(
        clean.app,
        ["corrupted", str(source), "--output", str(output), "--dry-run"],
    )

    assert result.exit_code == 0
    assert f"Source: {source}" in result.output
    assert f"Destination: {output / 'ignored' / 'corrupted'}" in result.output
    assert "Corrupted: 1" in result.output
    assert "Moved: 1" in result.output
    assert "Dry run: yes" in result.output


def test_clean_overexposed_ir_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    monkeypatch.setattr(
        clean,
        "run_clean_overexposed_ir",
        lambda input_data: CleanOverexposedIrResult(
            files_discovered=2,
            files_moved=1,
            files_overexposed=1,
            files_ignored=1,
            files_failed=0,
            destination=output / "ignored" / "overexposed",
            dry_run=False,
        ),
    )

    result = cli_runner.invoke(
        clean.app,
        ["overexposed-ir", str(source), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "Overexposed: 1" in result.output
    assert "Moved: 1" in result.output
    assert "Dry run: no" in result.output


def test_clean_bursts_prints_summary_for_success(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()

    monkeypatch.setattr(
        clean,
        "run_clean_bursts",
        lambda input_data: CleanBurstsResult(
            files_discovered=5,
            files_moved=2,
            files_ignored=3,
            files_bursts=1,
            files_reduced=2,
            files_failed=0,
            destination=output / "ignored" / "bursts",
            dry_run=False,
        ),
    )

    result = cli_runner.invoke(
        clean.app,
        ["bursts", str(source), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert "Bursts: 1" in result.output
    assert "Reduced: 2" in result.output
    assert "Moved: 2" in result.output


@pytest.mark.parametrize(
    ("command_name", "patched_runner", "result_factory", "extra_args"),
    [
        (
            "corrupted",
            "run_clean_corrupted",
            lambda destination: CleanCorruptedResult(
                files_failed=1,
                destination=destination,
            ),
            [],
        ),
        (
            "overexposed-ir",
            "run_clean_overexposed_ir",
            lambda destination: CleanOverexposedIrResult(
                files_failed=1,
                destination=destination,
            ),
            [],
        ),
        (
            "bursts",
            "run_clean_bursts",
            lambda destination: CleanBurstsResult(
                files_failed=1,
                destination=destination,
            ),
            [],
        ),
    ],
)
def test_clean_commands_exit_with_code_one_on_failures(
    cli_runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command_name: str,
    patched_runner: str,
    result_factory,
    extra_args: list[str],
):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    destination = output / "ignored"

    monkeypatch.setattr(clean, patched_runner, lambda input_data: result_factory(destination))

    result = cli_runner.invoke(
        clean.app,
        [command_name, str(source), "--output", str(output), *extra_args],
    )

    assert result.exit_code == 1
    assert "Failed: 1" in result.output
