# tests/test_cfg.py
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

import pytest

from fit_converter.cfg import effective_config, load_config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no FIT_CONVERTER_* vars interfere with tests."""
    to_clear = [k for k in os.environ if k.startswith("FIT_CONVERTER_")]
    for k in to_clear:
        monkeypatch.delenv(k, raising=False)


def write(p: Path, content: str):
    p.write_text(dedent(content).lstrip(), encoding="utf-8")


def test_defaults_only(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    cfg = effective_config(log=False)

    assert cfg["inbox"] == "inbox"
    assert cfg["outbox"] == "outbox"
    assert cfg["transform"] is True
    assert cfg["poll_interval"] == 0.5
    assert cfg["retries"] == 3

    assert "log_level" not in cfg

    log = cfg["logging"]
    assert log["level"] == "INFO"
    assert log["to_file"] is True
    assert isinstance(log["rotate_max_bytes"], int) and log["rotate_max_bytes"] > 0
    assert isinstance(log["backup_count"], int) and log["backup_count"] > 0

    # Derived file_path should use logs_dir
    expected = str(Path(cfg["logs_dir"]) / "fit-converter.log")
    assert log["file_path"] == expected


def test_example_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    write(
        tmp_path / "config.example.toml",
        """
        outbox = "example_out"
        log_level = "WARNING"
    """,
    )
    cfg = load_config()
    assert cfg["outbox"] == "example_out"
    assert cfg["log_level"] == "WARNING"


def test_main_overrides_example(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "config.example.toml", 'outbox = "example_out"\n')
    write(tmp_path / "config.toml", 'outbox = "main_out"\n')
    cfg = load_config()
    assert cfg["outbox"] == "main_out"


def test_local_overrides_main(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "config.toml", 'outbox = "main_out"\nlog_level = "WARNING"\n')
    write(tmp_path / "config.local.toml", 'outbox = "local_out"\nlog_level = "DEBUG"\n')
    cfg = load_config()
    assert cfg["outbox"] == "local_out"
    assert cfg["log_level"] == "DEBUG"


def test_env_overrides_all(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "config.toml", 'outbox = "main_out"\n')
    write(tmp_path / "config.local.toml", 'outbox = "local_out"\n')
    monkeypatch.setenv("FIT_CONVERTER_OUTBOX", "/env/out")
    cfg = load_config()
    assert cfg["outbox"] == "/env/out"


def test_type_coercion(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    # set via env to exercise coercion against _DEFAULTS
    monkeypatch.setenv("FIT_CONVERTER_TRANSFORM", "false")
    monkeypatch.setenv("FIT_CONVERTER_POLL_INTERVAL", "1.25")
    monkeypatch.setenv("FIT_CONVERTER_RETRIES", "7")
    cfg = load_config()
    assert cfg["transform"] is False
    assert cfg["poll_interval"] == 1.25
    assert cfg["retries"] == 7


def test_malformed_toml_does_not_crash(monkeypatch, tmp_path: Path, caplog):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text("this is : not toml", encoding="utf-8")
    cfg = load_config()
    # falls back to defaults since the TOML is malformed
    assert cfg["inbox"] == "inbox"
    # and we should have warned
    assert any("Malformed TOML" in rec.message for rec in caplog.records)
