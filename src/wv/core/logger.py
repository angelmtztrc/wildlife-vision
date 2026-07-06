import logging
from datetime import datetime

from rich.console import Console
from rich.measure import Measurement
from rich.progress import (
    BarColumn,
    Progress,
    Task,
    TextColumn,
    TimeElapsedColumn,
)
from rich.progress_bar import ProgressBar
from rich.segment import Segment
from rich.text import Text
from rich.traceback import Traceback

# --- Custom levels ---
# Standard levels: DEBUG=10, INFO=20, WARNING=30, ERROR=40
# DONE sits between INFO and WARNING so it always shows unless DEBUG is filtered.
DONE = 25
logging.addLevelName(DONE, "DONE")
logging.addLevelName(logging.WARNING, "WARN")  # display "WARN" instead of "WARNING"


def _done(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(DONE):
        self._log(DONE, message, args, **kwargs)


logging.Logger.done = _done  # adds logger.done("message")

# Color per log level (used inside the message via Rich markup)
LEVEL_COLORS = {
    "DEBUG": "dark_orange",
    "INFO": "blue",
    "DONE": "green",
    "WARN": "yellow",
    "ERROR": "red",
}

# --- Global verbose config ---
# When verbose is off, DEBUG messages are filtered out. When on, they're shown.
_verbose = False
_loggers: list[logging.Logger] = []
_console = Console()


class FullBlockProgressBar(ProgressBar):
    """Render a thicker-looking single-line progress bar with full block glyphs."""

    def __rich_console__(self, console, options):
        width = min(self.width or options.max_width, options.max_width)
        should_pulse = self.pulse or self.total is None
        if should_pulse:
            yield from self._render_pulse(console, width, ascii=options.legacy_windows)
            return

        completed = (
            min(self.total, max(0, self.completed)) if self.total is not None else None
        )
        complete_blocks = (
            int(width * completed / self.total)
            if self.total and completed is not None
            else width
        )
        remaining_blocks = max(0, width - complete_blocks)
        is_finished = self.total is None or self.completed >= self.total
        complete_style = console.get_style(
            self.finished_style if is_finished else self.complete_style
        )
        remaining_style = console.get_style(self.style)

        if complete_blocks:
            yield Segment("█" * complete_blocks, complete_style)
        if remaining_blocks:
            yield Segment("█" * remaining_blocks, remaining_style)

    def __rich_measure__(self, console, options):
        return (
            Measurement(self.width, self.width)
            if self.width is not None
            else Measurement(4, options.max_width)
        )


class FullBlockBarColumn(BarColumn):
    def render(self, task: Task) -> ProgressBar:
        return FullBlockProgressBar(
            total=max(0, task.total) if task.total is not None else None,
            completed=max(0, task.completed),
            width=None if self.bar_width is None else max(1, self.bar_width),
            pulse=not task.started,
            animation_time=task.get_time(),
            style=self.style,
            complete_style=self.complete_style,
            finished_style=self.finished_style,
            pulse_style=self.pulse_style,
        )


def set_verbose(verbose: bool) -> None:
    """Enable/disable DEBUG messages globally, for every logger created via get_logger.

    Call this once at startup, e.g. after parsing a --verbose CLI flag:
        set_verbose(args.verbose)
    """
    global _verbose
    _verbose = verbose
    level = logging.DEBUG if verbose else logging.INFO
    for logger in _loggers:
        logger.setLevel(level)


def reset_logging() -> None:
    """Reset logger state managed by this module back to its startup defaults."""
    global _verbose

    _verbose = False

    for logger in _loggers:
        logger.setLevel(logging.INFO)
        logger.propagate = False


class CustomFormatter(logging.Formatter):
    """Formats log records as: HH:MM:SS.sss [LEVEL] Scope: Message"""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class ConsoleLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            time_str = f"{time_str}.{int(record.msecs):03d}"

            log_line = Text()
            log_line.append(time_str, style="dim")
            log_line.append(" [")
            log_line.append(
                record.levelname, style=LEVEL_COLORS.get(record.levelname, "white")
            )
            log_line.append("] ")
            if _verbose:
                log_line.append(record.name, style="dim")
                log_line.append(": ")
            log_line.append(message)
            _console.print(log_line)

            if record.exc_info and record.exc_info != (None, None, None):
                exc_type, exc_value, exc_traceback = record.exc_info
                if (
                    exc_type is not None
                    and exc_value is not None
                    and exc_traceback is not None
                ):
                    _console.print(
                        Traceback.from_exception(
                            exc_type,
                            exc_value,
                            exc_traceback,
                        )
                    )
        except Exception:
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """Create (or reuse) a logger with the Rich-powered format above.

    'name' is used as the Scope in the log output, e.g. get_logger("Database")
    Its level is controlled globally by set_verbose().
    """
    logger = logging.getLogger(name)

    # Avoid attaching duplicate handlers if get_logger is called more than once
    if not logger.handlers:
        handler = ConsoleLogHandler()
        handler.setFormatter(CustomFormatter())

        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if _verbose else logging.INFO)
        logger.propagate = False  # don't double-log through the root logger

        _loggers.append(logger)

    return logger


def get_progress() -> Progress:
    """Create a Rich Progress bar for long-running processes.

    Usage:
        with get_progress() as progress:
            task = progress.add_task("Processing items...", total=100)
            for item in items:
                # do work
                progress.update(task, advance=1)
    """
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        FullBlockBarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=_console,
        expand=True,
    )
