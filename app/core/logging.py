"""
Structured logging configuration.

We use Python's standard logging module with a JSON-like format.
This keeps log lines machine-readable without adding a heavy
dependency like structlog.
"""

import logging
import sys


def configure_logging() -> None:
    """
    Set up root logger with a structured format.
    Call this once at application startup (in main.py).
    """
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Usage: logger = get_logger(__name__)"""
    return logging.getLogger(name)
