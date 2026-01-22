"""Logging utilities for CLI."""

import logging
import os
import sys


def setup_logging(log_level: str = None) -> None:
    """
    Setup logging with configurable level.
    
    Priority: argument > WOLO_LOG_LEVEL env var > default (WARNING)
    """
    # Determine log level: argument > env var > default
    if log_level is None:
        log_level = os.environ.get("WOLO_LOG_LEVEL", "WARNING")
    
    # Parse log level
    level = getattr(logging, log_level.upper(), logging.WARNING)

    # File handler - always DEBUG level for file
    file_handler = logging.FileHandler("wolo.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    # Console handler - configurable level
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure wolo loggers
    for logger_name in ["wolo", "aiohttp"]:
        log = logging.getLogger(logger_name)
        log.setLevel(logging.DEBUG)
        log.propagate = True
