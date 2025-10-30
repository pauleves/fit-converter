# tests/test_cfg_logging_shape.py
from pathlib import Path

from fit_converter.cfg import effective_config


def test_defaults_provide_complete_logging_section(tmp_path, monkeypatch):
    # Point cfg to a temp directory if your cfg respects CWD or env
    monkeypatch.chdir(tmp_path)
    cfg = effective_config(log=False)
    log = cfg["logging"]
    assert set(
        ["level", "to_file", "file_path", "rotate_max_bytes", "backup_count"]
    ).issubset(log.keys())
    assert Path(log["file_path"]).name == "fit-converter.log"  # derived from logs_dir
    assert cfg["logs_dir"] in str(log["file_path"])


def test_toml_overrides_file_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.toml").write_text(
        '[logging]\nlevel="DEBUG"\nfile_path="custom/path/app.log"\n'
    )
    cfg = effective_config(log=False)
    assert cfg["logging"]["level"] == "DEBUG"
    assert cfg["logging"]["file_path"].endswith("custom/path/app.log")
