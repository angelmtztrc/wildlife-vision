from collections.abc import Iterable, Sequence

from rich.console import Console
from rich.table import Table
from rich.text import Text


def print_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[object | None]],
    *,
    ratios: Sequence[int] | None = None,
    console: Console | None = None,
) -> None:
    """Print a borderless, terminal-width table for CLI list commands.

    Values render as literal, single-line text. Cells do not wrap and Rich uses
    ellipses when the terminal is too narrow for their full contents.
    """
    column_ratios = ratios or [1] * len(headers)
    if len(headers) != len(column_ratios):
        raise ValueError("Table headers and ratios must have the same length.")

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False, expand=True)
    for header, ratio in zip(headers, column_ratios, strict=True):
        table.add_column(header, ratio=ratio, no_wrap=True, overflow="ellipsis")
    for row in rows:
        if len(row) != len(headers):
            raise ValueError("Table row must contain one value per header.")
        table.add_row(*(_to_cell(value) for value in row))
    (console or Console()).print(table)


def _to_cell(value: object | None) -> Text:
    text = "" if value is None else " ".join(str(value).split())
    return Text(text)
