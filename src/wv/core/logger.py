import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

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
    "DEBUG": "cyan",
    "INFO": "blue",
    "DONE": "green",
    "WARN": "yellow",
    "ERROR": "red",
}

# --- Global verbose config ---
# When verbose is off, DEBUG messages are filtered out. When on, they're shown.
_verbose = False
_loggers: list[logging.Logger] = []


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


class CustomFormatter(logging.Formatter):
    """Formats log records as: HH:MM:SS.sss [LEVEL] Scope: Message"""

    def format(self, record: logging.LogRecord) -> str:
        time_str = self.formatTime(record, "%H:%M:%S") + f".{int(record.msecs):03d}"
        color = LEVEL_COLORS.get(record.levelname, "white")
        return (
            f"{time_str} [{color}][{record.levelname}][/{color}] "
            f"{record.name}: {record.getMessage()}"
        )


def get_logger(name: str) -> logging.Logger:
    """Create (or reuse) a logger with the Rich-powered format above.

    'name' is used as the Scope in the log output, e.g. get_logger("Database")
    Its level is controlled globally by set_verbose().
    """
    logger = logging.getLogger(name)

    # Avoid attaching duplicate handlers if get_logger is called more than once
    if not logger.handlers:
        handler = RichHandler(
            console=Console(),
            markup=True,  # let our [color]...[/color] tags work
            show_time=False,  # we print the time ourselves
            show_level=False,  # we print the level ourselves
            show_path=False,  # keep output clean/simple
            rich_tracebacks=True,  # nicer tracebacks on exceptions
        )
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
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
    )
