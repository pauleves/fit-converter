# fit_converter/logging_setup.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
_CONFIGURED = False  # guard against duplicate handlers


def configure_logging(
    level: str = "INFO",
    *,
    to_file: bool = True,
    file_path: str | None = None,
    rotate_max_bytes: int = 1_000_000,
    backup_count: int = 5,
    force: bool = False,  # set True only if you explicitly want to rebuild handlers
) -> None:
    """
    Configure root logging once. Safe to call multiple times (no duplicate handlers).
    Use `force=True` to rebuild handlers (rare).
    """
    global _CONFIGURED
    root = logging.getLogger()

    if _CONFIGURED and not force:
        # Still apply level updates if requested
        root.setLevel(_LEVELS.get(level.upper(), logging.INFO))
        return

    if force:
        for h in list(root.handlers):
            root.removeHandler(h)

    root.setLevel(_LEVELS.get(level.upper(), logging.INFO))

    fmt = "%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console handler (one)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # Optional rotating file handler
    if to_file and file_path:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(p, maxBytes=rotate_max_bytes, backupCount=backup_count)
        fh.setFormatter(formatter)
        root.addHandler(fh)

    # Route warnings.warn() into logging
    logging.captureWarnings(True)

    # (Nice touch) quiet noisy libs when running INFO/DEBUG
    try:
        logging.getLogger("werkzeug").setLevel(logging.INFO)  # Flask HTTP logs
        logging.getLogger("watchdog.observers").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    except Exception:
        pass

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Convenience helper; identical to logging.getLogger but clearer in imports."""
    return logging.getLogger(name or __name__)
