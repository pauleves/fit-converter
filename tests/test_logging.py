# tests/test_logging.py
from __future__ import annotations

import importlib
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


def _reset_logging_module():
    # Helper to clear the idempotency guard between tests
    from fit_converter import logging_setup as ls

    for h in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(h)
    if hasattr(ls.configure_logging, "_configured"):
        delattr(ls.configure_logging, "_configured")
    importlib.reload(ls)
    return ls


def test_creates_file_handler_and_console(monkeypatch, tmp_path):
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FIT_CONVERTER_LOGS_DIR", str(tmp_path / "state" / "logs"))

    ls = _reset_logging_module()
    from fit_converter.cfg import effective_config
    from fit_converter.paths import ensure_dirs

    paths = ensure_dirs()
    cfg = effective_config(log=False)

    ls.configure_logging(logs_dir=paths.logs_dir, logging_cfg=cfg["logging"])

    root, file_handlers, stream_handlers = _get_handlers()
    assert len(file_handlers) == 1, "Expected exactly one RotatingFileHandler"
    assert len(stream_handlers) >= 1, "Expected at least one console StreamHandler"

    logfile = Path(paths.logs_dir) / cfg["logging"]["filename"]
    assert file_handlers[0].baseFilename == str(logfile)
    assert logfile.parent.exists()


def test_configure_logging_no_explicit_path_needed(monkeypatch, tmp_path):
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FIT_CONVERTER_LOGS_DIR", str(tmp_path / "state" / "logs"))

    ls = _reset_logging_module()
    from fit_converter.cfg import effective_config
    from fit_converter.paths import ensure_dirs

    paths = ensure_dirs()
    cfg = effective_config(log=False)

    # Should NOT raise; writes to <logs_dir>/<filename>
    ls.configure_logging(logs_dir=paths.logs_dir, logging_cfg=cfg["logging"])

    _, file_handlers, _ = _get_handlers()
    expected = Path(paths.logs_dir) / cfg["logging"]["filename"]
    assert file_handlers and file_handlers[0].baseFilename == str(expected)


def test_idempotent_reconfigure_is_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FIT_CONVERTER_LOGS_DIR", str(tmp_path / "state" / "logs"))

    ls = _reset_logging_module()
    from fit_converter.cfg import effective_config
    from fit_converter.paths import ensure_dirs

    paths = ensure_dirs()
    cfg = effective_config(log=False)

    ls.configure_logging(
        logs_dir=paths.logs_dir, logging_cfg={**cfg["logging"], "level": "INFO"}
    )
    _, f1, s1 = _get_handlers()

    # Second call should be a no-op (guarded), not duplicate handlers
    ls.configure_logging(
        logs_dir=paths.logs_dir, logging_cfg={**cfg["logging"], "level": "ERROR"}
    )
    _, f2, s2 = _get_handlers()

    assert len(f2) == len(f1) == 1
    assert len(s2) == len(s1)
