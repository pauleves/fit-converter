# tests/test_logging.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _get_handlers():
    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    stream_handlers = [
        h for h in root.handlers if not isinstance(h, RotatingFileHandler)
    ]
    return root, file_handlers, stream_handlers


def test_creates_file_handler_and_console(monkeypatch, tmp_path):
    # Point logs to a temp dir via the new APP_* envs
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    from fit_converter.logging_setup import LOG_FILENAME, configure_logging
    from fit_converter.paths import ensure_dirs

    # Force a clean logging setup and attach both console + rotating file
    configure_logging(
        level="INFO",
        to_file=True,
        rotate_max_bytes=1000,
        backup_count=1,
        force=True,
    )

    root, file_handlers, stream_handlers = _get_handlers()
    assert len(file_handlers) == 1, "Expected exactly one RotatingFileHandler"
    assert len(stream_handlers) >= 1, "Expected at least one console StreamHandler"

    logfile = Path(ensure_dirs().logs_dir) / LOG_FILENAME
    assert file_handlers[0].baseFilename == str(logfile), "File handler path mismatch"
    assert logfile.parent.exists()


def test_configure_logging_no_explicit_path_needed(monkeypatch, tmp_path):
    # Old tests expected ValueError when no file path was passed; new API derives it.
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    from fit_converter.logging_setup import LOG_FILENAME, configure_logging
    from fit_converter.paths import ensure_dirs

    # Should NOT raise; should create a file handler pointing to <logs_dir>/fit-converter.log
    configure_logging(
        level="DEBUG",
        to_file=True,
        rotate_max_bytes=2048,
        backup_count=2,
        force=True,
    )

    root, file_handlers, _ = _get_handlers()
    assert len(file_handlers) == 1
    expected = Path(ensure_dirs().logs_dir) / LOG_FILENAME
    assert file_handlers[0].baseFilename == str(expected)


def test_idempotent_reconfigure_no_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    from fit_converter.logging_setup import configure_logging

    # First setup
    configure_logging(
        level="INFO",
        to_file=True,
        rotate_max_bytes=1000,
        backup_count=1,
        force=True,
    )
    _, file_handlers_1, stream_handlers_1 = _get_handlers()

    # Second setup without force should not duplicate handlers; only update levels.
    configure_logging(
        level="ERROR",
        to_file=True,
        rotate_max_bytes=1000,
        backup_count=1,
        force=False,
    )
    _, file_handlers_2, stream_handlers_2 = _get_handlers()

    assert len(file_handlers_2) == len(file_handlers_1) == 1
    assert len(stream_handlers_2) >= 1
    # Root level should reflect latest call
    assert logging.getLogger().level == logging.ERROR
