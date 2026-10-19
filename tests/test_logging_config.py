"""Tests for the logging configuration of `tsnetplus`."""

import io
import logging

from rich.logging import RichHandler

import tsnetplus
from tsnetplus.utils.logging_config import LoggingConfig, configure_logging


def _cleanup() -> None:
    """Remove handlers installed by :func:`configure_logging`."""
    logger = logging.getLogger("tsnetplus")
    for handler in logger.handlers[:]:
        if getattr(handler, "_tsnetplus_handler", False):
            logger.removeHandler(handler)
            handler.close()
    logger.handlers.clear()


def test_configure_logging_installs_handler_on_tsnetplus_logger():
    """`configure_logging` must configure the `tsnetplus` logger hierarchy.

    Regression test: the handler used to be installed on a logger named
    `tsnet`, which is not the name used by the package modules, so
    `configure_logging()` had no effect on the package log messages.
    """
    _cleanup()
    try:
        configure_logging(LoggingConfig(stream=io.StringIO()))

        handlers = [
            handler
            for handler in logging.getLogger("tsnetplus").handlers
            if getattr(handler, "_tsnetplus_handler", False)
        ]
        assert len(handlers) == 1
        assert isinstance(handlers[0], RichHandler)
    finally:
        _cleanup()


def test_configure_logging_does_not_configure_the_stale_tsnet_logger():
    """The stale `tsnet` logger must not be configured."""
    _cleanup()
    tsnet_logger = logging.getLogger("tsnet")
    tsnet_logger.handlers.clear()
    try:
        configure_logging(LoggingConfig(stream=io.StringIO()))
        assert tsnet_logger.handlers == []
    finally:
        tsnet_logger.handlers.clear()
        _cleanup()


def test_configure_logging_is_idempotent():
    """Calling `configure_logging` twice must not duplicate handlers."""
    _cleanup()
    try:
        stream = io.StringIO()
        configure_logging(LoggingConfig(stream=stream))
        configure_logging(LoggingConfig(stream=stream))

        handlers = [
            handler
            for handler in logging.getLogger("tsnetplus").handlers
            if getattr(handler, "_tsnetplus_handler", False)
        ]
        assert len(handlers) == 1
    finally:
        _cleanup()


def test_configure_logging_leaves_other_loggers_untouched():
    """The root logger must not be modified by `configure_logging`."""
    _cleanup()
    root_handlers = list(logging.getLogger().handlers)
    try:
        configure_logging(LoggingConfig(stream=io.StringIO()))
        assert logging.getLogger().handlers == root_handlers
    finally:
        _cleanup()


def test_configure_logging_sets_level_and_disables_propagation():
    """The configured level is applied and records do not reach the root."""
    _cleanup()
    try:
        configure_logging(LoggingConfig(level=logging.WARNING))
        logger = logging.getLogger("tsnetplus")
        assert logger.level == logging.WARNING
        assert logger.propagate is False
    finally:
        _cleanup()


def test_configure_logging_does_not_break_package_import():
    """The public helper remains importable from the package root."""
    assert tsnetplus.configure_logging is configure_logging
