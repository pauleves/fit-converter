# fit_converter/logging_setup.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal, TypedDict

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
    rotate_max_bytes: int
    backup_count: int


def configure_logging(*, logs_dir: str | Path, logging_cfg: dict) -> None:
    """
    Idempotent logging config.
    logs_dir: absolute directory for logs (from paths.logs_dir)
    logging_cfg: dict with keys level, to_file, rotate_max_bytes, backup_count, filename
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # keep root open; handlers decide what to emit

    lvl_name = logging_cfg.get("level", "INFO")
    lvl = getattr(logging, str(lvl_name).upper(), logging.INFO)

    # Avoid duplicate handlers if tests call this multiple times
    if getattr(configure_logging, "_configured", False):
        return

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(lvl)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] (%(threadName)s) %(message)s"
    )
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # File handler (optional)
    if logging_cfg.get("to_file", True):
        filename = logging_cfg.get("filename", "fit-converter.log")
        rotate_max_bytes = int(logging_cfg.get("rotate_max_bytes", 1_000_000))
        backup_count = int(logging_cfg.get("backup_count", 5))

        log_dir = Path(logs_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        p = log_dir / filename

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

        # Log once where the file is going
        root.info("File logging to %s", p)

    configure_logging._configured = True  # type: ignore[attr-defined]


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or __name__)
