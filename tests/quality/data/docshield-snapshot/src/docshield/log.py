"""Centralised logging configuration.

Console output uses human-readable format.  File output uses JSON lines
so logs can be parsed by monitoring tools in production.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_CONFIGURED = False


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record for machine-parseable file logs."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(
    log_dir: Path | None = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure the ``docshield`` logger with console and optional file output.

    - Console handler: human-readable, writes to stderr.
    - File handler (when *log_dir* is set): JSON-lines to ``docshield.log``.

    Calling this function more than once is a no-op so it is safe for tests.
    """
    global _CONFIGURED
    logger = logging.getLogger("docshield")

    if _CONFIGURED:
        return logger

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(console_fmt)
    logger.addHandler(console)

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "docshield.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(_JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
        logger.addHandler(fh)

    _CONFIGURED = True
    return logger


def reset_logging() -> None:
    """Remove all handlers and reset state.  Used by tests only."""
    global _CONFIGURED
    logger = logging.getLogger("docshield")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    _CONFIGURED = False


def get_logger(name: str = "docshield") -> logging.Logger:
    """Return a child logger under the ``docshield`` namespace."""
    return logging.getLogger(name)
