# tests/test_cfg_logging_shape.py
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fit_converter.cfg import effective_config
from fit_converter.logging_setup import configure_logging
from fit_converter.paths import ensure_dirs


def test_defaults_provide_complete_logging_section(tmp_path, monkeypatch):
    # Isolate to a temp area using the new env names
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FIT_CONVERTER_LOGS_DIR", str(tmp_path / "state" / "logs"))

    cfg = effective_config(log=False)
    log = cfg["logging"]

    # Schema (no file_path anymore)
    assert {"level", "to_file", "rotate_max_bytes", "backup_count", "filename"} <= set(
        log.keys()
    )

    # Configure logging with the resolved logs_dir + logging cfg
    paths = ensure_dirs()
    configure_logging(logs_dir=paths.logs_dir, logging_cfg=log)

    # Grab the single rotating file handler and compare paths
    import logging

    root = logging.getLogger()
    fhs = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(fhs) == 1

    expected = Path(paths.logs_dir) / log["filename"]
    assert Path(fhs[0].baseFilename) == expected
