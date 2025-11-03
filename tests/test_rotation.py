# tests/test_rotation.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def test_rotates_when_max_reached(monkeypatch, tmp_path):
    # Put logs in a temp dir
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    from fit_converter.logging_setup import LOG_FILENAME, configure_logging
    from fit_converter.paths import ensure_dirs

    # Start clean and set a tiny max so we trigger rotation quickly
    configure_logging(
        level="INFO",
        to_file=True,
        rotate_max_bytes=200,  # very small to force rollover
        backup_count=2,
        force=True,  # ensure no prior handlers leak in
    )

    logger = logging.getLogger("test.rotate")

    # Emit enough bytes to exceed 200B and trigger rollover
    big = "X" * 120
    for _ in range(10):
        logger.info(big)

    # Flush handlers to ensure files are written
    root = logging.getLogger()
    for h in root.handlers:
        if hasattr(h, "flush"):
            h.flush()

    log_dir = Path(ensure_dirs().logs_dir)
    base = log_dir / LOG_FILENAME
    rotated = log_dir / f"{LOG_FILENAME}.1"

    # Sanity: we have a rotating file handler attached
    assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    # Base log should exist
    assert base.exists(), f"Expected base log at {base}"

    # Rotation should have occurred -> ".1" should exist
    assert (
        rotated.exists()
    ), f"Expected rotated file {rotated} to exist after exceeding maxBytes"

    # And the base file should now be smaller than or around the threshold
    # (can't guarantee exact size due to line formatting, but rotation occurred)
    assert base.stat().st_size <= 200 or base.stat().st_size < rotated.stat().st_size
