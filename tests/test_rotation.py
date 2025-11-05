# tests/test_rotation.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def test_rotates_when_max_reached(monkeypatch, tmp_path):
    import importlib

    # --- reset logging state (avoid cross-test leakage / idempotency guard)
    for h in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(h)
    import fit_converter.logging_setup as ls

    if hasattr(ls.configure_logging, "_configured"):
        delattr(ls.configure_logging, "_configured")
    importlib.reload(ls)

    # --- direct logs to a temp dir using the new env names
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FIT_CONVERTER_LOGS_DIR", str(tmp_path / "state" / "logs"))

    from fit_converter.cfg import effective_config
    from fit_converter.logging_setup import configure_logging
    from fit_converter.paths import ensure_dirs

    paths = ensure_dirs()
    cfg = effective_config(log=False)

    # make rollover easy/fast
    cfg["logging"].update(
        {
            "level": "INFO",
            "to_file": True,
            "rotate_max_bytes": 200,  # tiny to force rollover
            "backup_count": 2,
        }
    )

    configure_logging(logs_dir=paths.logs_dir, logging_cfg=cfg["logging"])

    # Sanity: we have a rotating file handler on root
    root = logging.getLogger()
    rfh = next((h for h in root.handlers if isinstance(h, RotatingFileHandler)), None)
    assert rfh is not None, "Expected a RotatingFileHandler to be attached"

    # Emit enough bytes to exceed 200B and trigger rollover
    big = "X" * 120
    for _ in range(10):
        root.info(big)

    # Flush handlers to ensure files are written
    for h in root.handlers:
        if hasattr(h, "flush"):
            h.flush()

    base = Path(paths.logs_dir) / cfg["logging"]["filename"]
    rotated = Path(paths.logs_dir) / f"{cfg['logging']['filename']}.1"

    # Base log should exist
    assert base.exists(), f"Expected base log at {base}"

    # Rotation should have occurred -> ".1" should exist
    assert rotated.exists(), f"Expected rotated file {rotated} to exist"

    # Base should now be <= threshold (roughly) or smaller than rotated
    assert base.stat().st_size <= 200 or base.stat().st_size < rotated.stat().st_size
