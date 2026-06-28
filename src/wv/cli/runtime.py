import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from rich.console import Console
from rich.text import Text

OK_LEVEL = logging.INFO + 5
_DEFAULT_LOG_LEVEL = logging.INFO
_LEVEL_STYLES = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
    "OK": "green",
}


@dataclass(frozen=True)
class CliRuntime:
    verbose: bool
    log_level: int
    show_summary_table: bool
    progress_enabled: bool
    stdout_console: Console
    stderr_console: Console


class RichConsoleHandler(logging.Handler):
    def __init__(self, console: Console):
        super().__init__()
        self.console = console

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info:
                message = (
                    f"{message}\n{self.formatter.formatException(record.exc_info)}"
                    if message
                    else self.formatter.formatException(record.exc_info)
                )

            self.console.print(
                build_event_text(
                    level_name=record.levelname,
                    message=message,
                    created=record.created,
                ),
                soft_wrap=True,
            )
        except Exception:
            self.handleError(record)


_runtime: CliRuntime | None = None


def _ok(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(OK_LEVEL):
        self._log(OK_LEVEL, message, args, **kwargs)


def install_ok_level() -> None:
    if logging.getLevelName(OK_LEVEL) != "OK":
        logging.addLevelName(OK_LEVEL, "OK")

    if not hasattr(logging.Logger, "ok"):
        setattr(logging.Logger, "ok", _ok)


def _format_timestamp(created: float | None = None) -> str:
    timestamp = datetime.fromtimestamp(created or datetime.now().timestamp())
    return f"{timestamp.strftime('%H:%M:%S')}.{int(timestamp.microsecond / 1000):03d}"


def build_event_text(level_name: str, message: str, created: float | None = None) -> Text:
    normalized_level_name = "WARNING" if level_name == "WARN" else level_name
    display_level_name = "WARN" if normalized_level_name == "WARNING" else normalized_level_name
    level_style = _LEVEL_STYLES.get(normalized_level_name, "white")

    event = Text()
    event.append(f"<{_format_timestamp(created)}> ", style="dim")
    event.append("[", style="dim")
    event.append(display_level_name, style=level_style)
    event.append("] ", style="dim")
    event.append(message)
    return event


def render_event_line(
    console: Console,
    *,
    level_name: str,
    message: str,
    created: float | None = None,
) -> None:
    console.print(
        build_event_text(level_name=level_name, message=message, created=created),
        soft_wrap=True,
    )


def configure_runtime(verbose: bool) -> CliRuntime:
    global _runtime

    install_ok_level()

    runtime = CliRuntime(
        verbose=verbose,
        log_level=logging.DEBUG if verbose else _DEFAULT_LOG_LEVEL,
        show_summary_table=verbose,
        progress_enabled=True,
        stdout_console=Console(stderr=False),
        stderr_console=Console(stderr=True),
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(runtime.log_level)

    handler = RichConsoleHandler(runtime.stderr_console)
    handler.setLevel(runtime.log_level)
    handler.setFormatter(logging.Formatter())
    root_logger.addHandler(handler)

    _runtime = runtime
    return runtime


def get_runtime() -> CliRuntime:
    if _runtime is None:
        return configure_runtime(verbose=False)

    return _runtime


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def reset_runtime() -> None:
    global _runtime

    logging.getLogger().handlers.clear()
    _runtime = None


@contextmanager
def status(runtime: CliRuntime, message: str) -> Iterator[None]:
    if runtime.progress_enabled and runtime.verbose:
        with runtime.stderr_console.status(message):
            yield
        return

    yield
