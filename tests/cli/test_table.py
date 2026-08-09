from io import StringIO

from rich.console import Console

from wv.cli.table import print_table


def test_print_table_uses_literal_single_line_cells_with_headers():
    output = StringIO()
    console = Console(file=output, width=100, force_terminal=False)

    print_table(
        ["ID", "NAME"],
        [("[red]ID[/red]", "First\nSecond\tThird")],
        console=console,
    )

    rendered = output.getvalue()
    assert "ID" in rendered
    assert "NAME" in rendered
    assert "[red]ID[/red]" in rendered
    assert "First Second Third" in rendered
    assert "╭" not in rendered


def test_print_table_keeps_headers_when_empty():
    output = StringIO()

    print_table(["ID", "NAME"], [], console=Console(file=output, force_terminal=False))

    assert "ID" in output.getvalue()
    assert "NAME" in output.getvalue()


def test_print_table_ellipsizes_narrow_columns_without_wrapping():
    output = StringIO()

    print_table(
        ["LONG HEADER", "VALUE"],
        [("a very long identifier", "a very long value")],
        console=Console(file=output, width=20, force_terminal=False),
    )

    rendered = output.getvalue()
    assert "…" in rendered
    assert len(rendered.strip().splitlines()) == 2
