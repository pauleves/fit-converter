# tests/test_cfg_logging_shape.py
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fit_converter.cfg import effective_config
from fit_converter.logging_setup import LOG_FILENAME, configure_logging
from fit_converter.paths import ensure_dirs


def test_defaults_provide_complete_logging_section(tmp_path, monkeypatch):
    # Isolate config/state so nothing from the real machine leaks in
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("APP_LOGS_DIR", str(tmp_path / "state" / "logs"))

    cfg = effective_config(log=False)
    log = cfg["logging"]

    # 1) Schema check (no file_path any more)
    assert {"level", "to_file", "rotate_max_bytes", "backup_count"} <= set(log.keys())

    # 2) Behaviour check: configure and assert the file handler path
    configure_logging(
        level=log["level"],
        to_file=log["to_file"],
        rotate_max_bytes=log["rotate_max_bytes"],
        backup_count=log["backup_count"],
        force=True,  # ensure a clean root logger for this test
    )

    # Grab the single rotating file handler and compare paths
    import logging

    root = logging.getLogger()
    fhs = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
    assert len(fhs) == 1

    expected = Path(ensure_dirs().logs_dir) / LOG_FILENAME
    assert Path(fhs[0].baseFilename) == expected
