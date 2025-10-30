# tests/test_logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from fit_converter.logging_setup import configure_logging


def _reset_root():
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.NOTSET)


@pytest.fixture(autouse=True)
def clean_logging_root():
    _reset_root()
    yield
    _reset_root()


def test_creates_file_handler_and_console(tmp_path: Path):
    log_file = tmp_path / "logs" / "fit-converter.log"
    configure_logging(
        level="INFO",
        to_file=True,
        file_path=str(log_file),
        rotate_max_bytes=1_000_000,
        backup_count=5,
    )
    root = logging.getLogger()
    handlers = root.handlers
    assert any(
        isinstance(h, logging.StreamHandler) and not hasattr(h, "baseFilename")
        for h in handlers
    )
    fh = next(h for h in handlers if isinstance(h, RotatingFileHandler))
    assert fh.baseFilename == str(log_file)
    assert log_file.parent.exists()


def test_level_mapping_applied():
    configure_logging(
        level="DEBUG",
        to_file=False,
        file_path=None,
        rotate_max_bytes=1_000_000,
        backup_count=5,
    )
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    # handler levels aligned too
    assert all(h.level == logging.DEBUG for h in root.handlers)


def test_idempotent_second_call_adds_no_duplicate_handlers(tmp_path: Path):
    log_file = tmp_path / "app.log"
    configure_logging(
        level="INFO",
        to_file=True,
        file_path=str(log_file),
        rotate_max_bytes=1_000_000,
        backup_count=5,
    )
    first = tuple(logging.getLogger().handlers)
    configure_logging(
        level="INFO",
        to_file=True,
        file_path=str(log_file),
        rotate_max_bytes=1_000_000,
        backup_count=5,
    )
    second = tuple(logging.getLogger().handlers)
    assert first == second  # no duplicates


def test_force_rebuilds_handlers(tmp_path: Path):
    log_file = tmp_path / "a.log"
    configure_logging(
        level="INFO",
        to_file=True,
        file_path=str(log_file),
        rotate_max_bytes=1_000_000,
        backup_count=5,
    )
    before = tuple(logging.getLogger().handlers)
    configure_logging(
        level="WARNING",
        to_file=False,
        file_path=None,
        rotate_max_bytes=1_000_000,
        backup_count=5,
        force=True,
    )
    after = tuple(logging.getLogger().handlers)
    assert before != after
    assert logging.getLogger().level == logging.WARNING
    # now only console handler should exist
    assert any(
        isinstance(h, logging.StreamHandler) and not hasattr(h, "baseFilename")
        for h in after
    )
    assert not any(isinstance(h, RotatingFileHandler) for h in after)


def test_to_file_requires_path_when_true():
    # Only include this if you added the guard in configure_logging
    with pytest.raises(ValueError):
        configure_logging(
            level="INFO",
            to_file=True,
            file_path=None,
            rotate_max_bytes=1_000_000,
            backup_count=5,
        )
