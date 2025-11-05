# tests/test_cfg.py
from __future__ import annotations

import os
from pathlib import Path

import pytest

from fit_converter.cfg import effective_config, load_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Ensure no ambient config/env leaks into tests
    for k in list(os.environ):
        if k.startswith("FIT_CONVERTER_") or k.startswith("APP_"):
            monkeypatch.delenv(k, raising=False)


def test_load_defaults_from_env_only(monkeypatch, tmp_path: Path):
    # No files; loader should use in-code defaults + ENV only
    # (If you support FIT_CONVERTER_CONFIG_DIR, it can be set here, but not required.)
    cfg = load_config()

    # Flat keys (pre-resolution)
    assert cfg["inbox"] == "inbox"
    assert cfg["outbox"] == "outbox"
    assert cfg["transform"] is True
    assert cfg["poll_interval"] == 0.5
    assert cfg["retries"] == 3

    # Logging block (new schema; no legacy file_path/log_level)
    log = cfg["logging"]
    assert log["level"] in {"INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"}
    assert log["to_file"] is True
    assert isinstance(log["rotate_max_bytes"], int) and log["rotate_max_bytes"] > 0
    assert isinstance(log["backup_count"], int) and log["backup_count"] > 0
    assert isinstance(log["filename"], str) and len(log["filename"]) > 0


def test_env_overrides_all(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FIT_CONVERTER_OUTBOX", "/env/out")
    monkeypatch.setenv("FIT_CONVERTER_RETRIES", "7")

    cfg = load_config()
    assert cfg["outbox"] == "/env/out"
    assert cfg["retries"] == 7


def test_type_coercion(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FIT_CONVERTER_TRANSFORM", "false")
    monkeypatch.setenv("FIT_CONVERTER_POLL_INTERVAL", "1.25")
    monkeypatch.setenv("FIT_CONVERTER_RETRIES", "9")

    cfg = load_config()
    assert cfg["transform"] is False
    assert cfg["poll_interval"] == 1.25
    assert cfg["retries"] == 9


def test_effective_config_resolves_absolute_paths(monkeypatch, tmp_path: Path):
    # When runtime roots are set, effective_config should reflect absolute leaf paths
    monkeypatch.setenv("FIT_CONVERTER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FIT_CONVERTER_STATE_DIR", str(tmp_path / "state"))

    cfg = effective_config(log=False)
    assert Path(cfg["inbox"]).is_absolute()
    assert Path(cfg["outbox"]).is_absolute()
    assert Path(cfg["logs_dir"]).is_absolute()
