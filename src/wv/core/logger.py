import io
import logging
import warnings
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime

from rich.console import Console
from rich.measure import Measurement
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
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
_quiet_library_loggers = ("PIL", "megadetector")


class FullBlockProgressBar(ProgressBar):
    """Internal Rich progress bar that renders full-block glyphs."""

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
    """Internal Rich column that creates ``FullBlockProgressBar`` instances."""

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
    """Set the global verbosity for every logger created by this module.

    Args:
        verbose: Whether managed loggers should emit ``DEBUG`` records.

    Notes:
        This mutates process-wide logger state. Call it during application
        startup after parsing the root CLI verbosity option.
    """
    global _verbose
    _verbose = verbose
    level = logging.DEBUG if verbose else logging.INFO
    for logger in _loggers:
        logger.setLevel(level)


def reset_logging() -> None:
    """Reset logging state managed by this module to startup defaults.

    Resets managed logger levels and propagation, quiet-library logger levels,
    warning filters, and global verbosity. This is intended for test fixtures
    and process-reset support rather than normal command execution.
    """
    global _verbose

    _verbose = False

    for logger in _loggers:
        logger.setLevel(logging.INFO)
        logger.propagate = False

    for logger_name in _quiet_library_loggers:
        logging.getLogger(logger_name).setLevel(logging.NOTSET)

    warnings.resetwarnings()


class CustomFormatter(logging.Formatter):
    """Internal formatter that returns only the rendered log message."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


class ConsoleLogHandler(logging.Handler):
    """Internal Rich handler that applies timestamps, levels, and tracebacks."""

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
    """Create or reuse a Rich-backed logger managed by this module.

    Args:
        name: Logger name used as the verbose-mode output scope.

    Returns:
        A non-propagating logger with one Rich console handler. Its level tracks
        the current global verbosity and it has a dynamically attached
        ``logger.done(...)`` method for completion messages.

    Notes:
        The dynamic ``done`` method is available at runtime but is not declared
        on ``logging.Logger`` for static type checkers.
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


def configure_external_output(verbose: bool) -> None:
    """Configure third-party logger levels and warning filtering.

    Args:
        verbose: Whether managed third-party libraries should emit ``DEBUG``
            records instead of being limited to warnings.

    Notes:
        This mutates process-wide logger levels and warning filters for PIL and
        MegaDetector. Call it during application startup.
    """
    library_log_level = logging.DEBUG if verbose else logging.WARNING

    for logger_name in _quiet_library_loggers:
        logging.getLogger(logger_name).setLevel(library_log_level)

    warnings.resetwarnings()
    if not verbose:
        warnings.filterwarnings("ignore", module=r"^(PIL|megadetector)(\.|$)")


@contextmanager
def capture_external_output(logger: logging.Logger, scope: str):
    """Capture stdout and stderr from a block and log them in verbose mode.

    Args:
        logger: Managed logger that receives captured output at ``DEBUG`` level.
        scope: Description included with captured output messages.

    Yields:
        Control to the wrapped block while process stdout and stderr are
        redirected to in-memory buffers.

    Notes:
        Redirection is process-global for the duration of the context. Captured
        output is discarded unless global verbose logging is enabled.
    """
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        yield

    if not _verbose:
        return

    captured_stdout = stdout_buffer.getvalue().strip()
    captured_stderr = stderr_buffer.getvalue().strip()

    if captured_stdout:
        logger.debug("Captured stdout from %s:\n%s", scope, captured_stdout)

    if captured_stderr:
        logger.debug("Captured stderr from %s:\n%s", scope, captured_stderr)


def get_progress() -> Progress:
    """Create the configured Rich progress display for long-running work.

    Returns:
        A Rich ``Progress`` instance configured for this application's console.
        Each row starts with the local time when this display was created and an
        ``INFO`` level label, followed by the bar, percentage, completed count,
        and elapsed time. Use it as a context manager so terminal rendering is
        started and stopped correctly.

    Examples:
        with get_progress() as progress:
            task = progress.add_task("Processing items...", total=100)
            for item in items:
                # do work
                progress.update(task, advance=1)
    """
    started_at = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    info_color = LEVEL_COLORS["INFO"]

    return Progress(
        TextColumn(f"[dim]{started_at}[/dim] [[{info_color}]INFO[/{info_color}]]"),
        FullBlockBarColumn(bar_width=None),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=_console,
        expand=True,
    )
"""Process-wide Rich logging and progress helpers for application code."""
