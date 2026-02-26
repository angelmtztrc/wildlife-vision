from abc import ABC, abstractmethod
import sys
from typing import Any


class LoggerAdapter(ABC):
    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def exception(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def bind(self, **kwargs: Any) -> "LoggerAdapter": ...


class LoguruAdapter(LoggerAdapter):
    _is_configured = False

    @classmethod
    def _configure(cls) -> None:
        if cls._is_configured:
            return

        from loguru import logger as loguru_logger

        loguru_logger.configure(extra={"component": "wv"})

        loguru_logger.remove()  # Remove default handler
        loguru_logger.add(
            sys.stderr,
            level="INFO",
            colorize=True,
            backtrace=False,
            diagnose=False,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level:<8}</level> | "
                "<cyan>{extra[component]:<24}</cyan> | "
                "<level>{message}</level>"
            ),
        )

        cls._is_configured = True

    def __init__(self, name: str | None = None, *, _logger=None):
        self._configure()

        if _logger is not None:
            self._logger = _logger
        else:
            from loguru import logger as loguru_logger

            self._logger = loguru_logger.bind(component=name) if name else loguru_logger

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        self._logger.exception(message, **kwargs)

    def bind(self, **kwargs: Any) -> "LoguruAdapter":
        return LoguruAdapter(_logger=self._logger.bind(**kwargs))


_default_adapter: type[LoggerAdapter] = LoguruAdapter


def set_logging_adapter(adapter: type[LoggerAdapter]) -> None:
    global _default_adapter
    _default_adapter = adapter


def get_logger(name: str | None = None) -> LoggerAdapter:
    return _default_adapter(name)
