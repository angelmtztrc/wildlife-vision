from collections.abc import Sequence

from rich import box
from rich.table import Table

from wv.cli.runtime import CliRuntime, render_event_line


def _stringify_rows(rows: Sequence[tuple[str, object]]) -> list[tuple[str, str]]:
    return [(label, str(value)) for label, value in rows]


def _build_summary_message(message: str, rows: Sequence[tuple[str, object]]) -> str:
    if not rows:
        return message

    row_summary = ". ".join(f"{label}: {value}" for label, value in _stringify_rows(rows))
    return f"{message} {row_summary}."


def render_summary_table(
    runtime: CliRuntime,
    *,
    title: str,
    rows: Sequence[tuple[str, object]],
) -> None:
    table = Table(title=title, box=box.ROUNDED, show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    for label, value in _stringify_rows(rows):
        table.add_row(label, value)

    runtime.stdout_console.print(table)


def render_command_summary(
    runtime: CliRuntime,
    *,
    title: str,
    message: str,
    rows: Sequence[tuple[str, object]],
    level_name: str = "OK",
) -> None:
    render_event_line(
        runtime.stdout_console,
        level_name=level_name,
        message=_build_summary_message(message, rows),
    )

    if runtime.show_summary_table:
        render_summary_table(runtime, title=title, rows=rows)
