# tests/test_cfg.py
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest

from fit_converter.cfg import effective_config, load_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Ensure no ambient config/env leaks into tests
    for k in list(os.environ):
        if k.startswith("FIT_CONVERTER_") or k.startswith("APP_"):
            monkeypatch.delenv(k, raising=False)


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dedent(content).lstrip(), encoding="utf-8")


def test_load_defaults_only_uses_platform_config_dir(monkeypatch, tmp_path: Path):
    # No files present → defaults from loader
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "config"))
    cfg = load_config()

    # Flat keys (pre-resolution)
    assert cfg["inbox"] == "inbox"
    assert cfg["outbox"] == "outbox"
    assert cfg["transform"] is True
    assert cfg["poll_interval"] == 0.5
    assert cfg["retries"] == 3

    # Logging block (new schema; no legacy file_path/log_level)
    log = cfg["logging"]
    assert log["level"] == "INFO"
    assert log["to_file"] is True
    assert isinstance(log["rotate_max_bytes"], int) and log["rotate_max_bytes"] > 0
    assert isinstance(log["backup_count"], int) and log["backup_count"] > 0


def test_main_and_local_toml_precedence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "cfg"))
    cfgdir = tmp_path / "cfg"
    write(cfgdir / "config.toml", 'outbox = "main_out"\n[logging]\nlevel="WARNING"\n')
    write(
        cfgdir / "config.local.toml", 'outbox = "local_out"\n[logging]\nlevel="DEBUG"\n'
    )

    cfg = load_config()
    assert cfg["outbox"] == "local_out"
    assert cfg["logging"]["level"] == "DEBUG"


def test_env_overrides_all(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "cfg"))
    write(tmp_path / "cfg" / "config.toml", 'outbox = "main_out"\n')

    monkeypatch.setenv("FIT_CONVERTER_OUTBOX", "/env/out")
    monkeypatch.setenv("FIT_CONVERTER_RETRIES", "7")

    cfg = load_config()
    assert cfg["outbox"] == "/env/out"
    assert cfg["retries"] == 7


def test_type_coercion(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("FIT_CONVERTER_TRANSFORM", "false")
    monkeypatch.setenv("FIT_CONVERTER_POLL_INTERVAL", "1.25")
    monkeypatch.setenv("FIT_CONVERTER_RETRIES", "9")

    cfg = load_config()
    assert cfg["transform"] is False
    assert cfg["poll_interval"] == 1.25
    assert cfg["retries"] == 9


def test_malformed_toml_does_not_crash(monkeypatch, tmp_path: Path, caplog):
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cfg" / "config.toml").write_text(
        "this is : not toml", encoding="utf-8"
    )

    cfg = load_config()
    # Falls back to defaults
    assert cfg["inbox"] == "inbox"
    # Warned about malformed TOML
    assert any("Malformed TOML" in rec.message for rec in caplog.records)


def test_effective_config_resolves_absolute_paths(monkeypatch, tmp_path: Path):
    # When runtime roots are set, effective_config should reflect absolute leaf paths
    monkeypatch.setenv("APP_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APP_STATE_DIR", str(tmp_path / "state"))

    cfg = effective_config(log=False)
    assert Path(cfg["inbox"]).is_absolute()
    assert Path(cfg["outbox"]).is_absolute()
    assert Path(cfg["logs_dir"]).is_absolute()
