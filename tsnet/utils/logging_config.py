""" """
from __future__ import annotations
import logging
import sys
from dataclasses import dataclass
from typing import Final, TextIO
from rich.console import Console
from rich.logging import RichHandler


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Configuration for TSNet logging."""
    level: int = logging.INFO
    show_time: bool = True
    show_level: bool = True
    show_path: bool = True
    rich_tracebacks: bool = True
    markup: bool = True
    stream: TextIO = sys.stderr


def configure_logging(config: LoggingConfig | None = None) -> None:
    """Configure Rich-based logging for TSNet.

    This function configures only the ``tsnet`` logger hierarchy and
    does not modify the root logger or logging configuration of other
    packages.

    Parameters
    ----------
    config:
        Logging configuration. If ``None``, default settings are used.
    """
    config = config or LoggingConfig()
    logger = logging.getLogger("tsnet")
    console = Console(file=config.stream)
    handler = RichHandler(
        console=console,
        show_time=config.show_time,
        show_level=config.show_level,
        show_path=config.show_path,
        rich_tracebacks=config.rich_tracebacks,
        markup=config.markup,
    )
    logger.setLevel(config.level)
    logger.propagate = False
    # Remove handlers previously installed by TSNet.
    for existing_handler in logger.handlers[:]:
        if getattr(existing_handler, "_tsnet_handler", False):
            logger.removeHandler(existing_handler)
            existing_handler.close()
    handler._tsnet_handler = True
    logger.addHandler(handler)
