import io
import re
from datetime import datetime

from rich.console import Console

import wv.core.logger as logger


class _FixedDatetime(datetime):
    value = datetime(2026, 8, 10, 12, 34, 56, 789000)

    @classmethod
    def now(cls, tz=None):
        return cls.value.replace(tzinfo=tz)


def test_get_progress_renders_fixed_info_prefix(
    monkeypatch,
):
    output = io.StringIO()
    monkeypatch.setattr(
        logger,
        "_console",
        Console(file=output, force_terminal=False, color_system=None, width=120),
    )
    monkeypatch.setattr(logger, "datetime", _FixedDatetime)
    current_time = 0.0

    progress = logger.get_progress()
    _FixedDatetime.value = datetime(2026, 8, 10, 12, 35, 0)
    progress.get_time = lambda: current_time

    with progress:
        task = progress.add_task("Hidden task description", total=10)
        current_time = 3723.0
        progress.update(task, advance=10)

    rendered = output.getvalue().strip()

    assert re.fullmatch(
        r"12:34:56\.789 \[INFO\] █+ 100% 10/10 1:02:03", rendered
    )
    assert "Hidden task description" not in rendered
    assert "⠋" not in rendered
