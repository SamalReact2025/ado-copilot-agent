"""Structured logging configuration for ado-copilot-agent"""

import logging
import logging.handlers
from pathlib import Path
import sys


def _get_log_path() -> Path:
    """Return the log file path under the user config directory."""
    log_dir = Path.home() / ".ado-copilot-agent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "ado-copilot-agent.log"


def _configure_root_logger() -> None:
    """Configure the root logger once with file + console handlers."""
    root = logging.getLogger("ado_copilot_agent")
    if root.handlers:
        # Already configured — don't add duplicate handlers
        return

    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — DEBUG and above
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            _get_log_path(),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # If we can't write the log file, fall back gracefully
        pass

    # Console handler — WARNING and above only (Rich handles user-facing output)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger under the 'ado_copilot_agent' hierarchy.

    Usage:
        from utilities.logging_helper import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    _configure_root_logger()
    return logging.getLogger(f"ado_copilot_agent.{name}")
