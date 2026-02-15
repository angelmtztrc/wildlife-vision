from abc import ABC, abstractmethod
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
    def __init__(self, name: str | None = None, *, _logger=None):
        if _logger is not None:
            self._logger = _logger
        else:
            from loguru import logger as loguru_logger

            self._logger = loguru_logger.bind(name=name) if name else loguru_logger

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
