# fit_converter/logging_setup.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal, TypedDict

from fit_converter.paths import ensure_dirs

Level = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
LOG_FILENAME = "fit-converter.log"

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
    rotate_max_bytes: int
    backup_count: int


def configure_logging(
    *,
    level: Level,
    to_file: bool,
    rotate_max_bytes: int,
    backup_count: int,
    force: bool = False,
) -> None:
    """
    Configure root logging once.
    Console is always attached; file handler writes to <logs_dir>/fit-converter.log
    when to_file=True.
    """
    global _CONFIGURED
    root = logging.getLogger()

    # Normalise level
    lvl = _LEVELS.get(str(level).upper(), logging.INFO)
    root.setLevel(lvl)

    if _CONFIGURED and not force:
        for h in root.handlers:
            h.setLevel(lvl)
        # ensure console exists
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
        # ensure file exists if requested
        if to_file and not any(
            isinstance(h, RotatingFileHandler) for h in root.handlers
        ):
            p = Path(ensure_dirs().logs_dir) / LOG_FILENAME
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
        for n, sub_level in (
            ("werkzeug", logging.INFO),
            ("watchdog.observers", logging.WARNING),
            ("urllib3", logging.WARNING),
        ):
            logging.getLogger(n).setLevel(sub_level)
        return

    if force:
        for h in list(root.handlers):
            root.removeHandler(h)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # console
    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # file
    if to_file:
        p = Path(ensure_dirs().logs_dir) / LOG_FILENAME
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
    for n, sub_level in (
        ("werkzeug", logging.INFO),
        ("watchdog.observers", logging.WARNING),
        ("urllib3", logging.WARNING),
    ):
        logging.getLogger(n).setLevel(sub_level)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or __name__)
