# fit_converter/logging_setup.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal, Optional, TypedDict

Level = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}
_CONFIGURED = False  # guard against duplicate handlers


class LoggingConfig(TypedDict, total=False):
    level: Level
    to_file: bool
    file_path: Optional[str]
    rotate_max_bytes: int
    backup_count: int


def configure_logging(
    *,
    level: Level,
    to_file: bool,
    file_path: Optional[str],
    rotate_max_bytes: int,
    backup_count: int,
    force: bool = False,
) -> None:
    """
    Configure root logging once. Safe to call multiple times:
    - If already configured, we still update the level and attach any missing handlers
      (e.g., late-provided file handler).
    - Use force=True to rebuild handlers from scratch.
    """
    if to_file and not file_path:
        raise ValueError("to_file=True requires a non-empty logging.file_path")

    global _CONFIGURED
    root = logging.getLogger()

    # Always normalize level
    lvl = _LEVELS.get(str(level).upper(), logging.INFO)
    root.setLevel(lvl)

    # If already configured and not forcing, ensure required handlers exist and align levels
    if _CONFIGURED and not force:
        # Align existing handler levels and formatter
        for h in root.handlers:
            h.setLevel(lvl)
        # Ensure console handler exists
        if not any(
            isinstance(h, logging.StreamHandler) and not hasattr(h, "baseFilename")
            for h in root.handlers
        ):
            ch = logging.StreamHandler()
            ch.setLevel(lvl)
            ch.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            root.addHandler(ch)
        # Ensure file handler exists if requested and path provided (idempotent upgrade)
        if (
            to_file
            and file_path
            and not any(isinstance(h, RotatingFileHandler) for h in root.handlers)
        ):
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                p,
                maxBytes=rotate_max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
                delay=True,
            )
            fh.setLevel(lvl)
            fh.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            root.addHandler(fh)

        logging.captureWarnings(True)
        try:
            logging.getLogger("werkzeug").setLevel(logging.INFO)
            logging.getLogger("watchdog.observers").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)
        except Exception:
            pass
        return

    # Fresh (re)build when not configured or force=True
    if force:
        for h in list(root.handlers):
            root.removeHandler(h)

    fmt = "%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # Optional rotating file
    if to_file and file_path:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            p,
            maxBytes=rotate_max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
        fh.setLevel(lvl)
        fh.setFormatter(formatter)
        root.addHandler(fh)

    logging.captureWarnings(True)
    try:
        logging.getLogger("werkzeug").setLevel(logging.INFO)
        logging.getLogger("watchdog.observers").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    except Exception:
        pass

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Convenience helper; identical to logging.getLogger but clearer in imports."""
    return logging.getLogger(name or __name__)
