# src/fit_converter/doctor.py
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Tuple

from fit_converter.cfg import effective_config
from fit_converter.paths import ensure_dirs


def _rwx(dirpath: Path) -> Tuple[bool, bool, bool]:
    """Return (readable, writable, executable) for a directory path."""
    try:
        r = os.access(dirpath, os.R_OK)
        w = os.access(dirpath, os.W_OK)
        x = os.access(dirpath, os.X_OK)
        return r, w, x
    except Exception:
        return False, False, False


def _fmt_perm(r: bool, w: bool, x: bool) -> str:
    return f"{'r' if r else '-'}{'w' if w else '-'}{'x' if x else '-'}"


def _check_dir(
    label: str, p: Path, want_write: bool = True, check_space: bool = False
) -> None:
    exists = p.exists()
    r, w, x = _rwx(p if exists else p.parent)
    perms = _fmt_perm(r, w, x)
    print(f"  {label:<10}: {p}  [{perms}] {'(exists)' if exists else '(missing)'}")

    if not exists:
        print("    → Suggest: ensure directory exists and is accessible.")
        return
    if not r:
        print("    → Warning: not readable.")
    if want_write and not w:
        print("    → Warning: not writable (you may need different user/permissions).")
    if not x:
        print("    → Warning: not traversable (execute bit).")

    if check_space:
        try:
            usage = shutil.disk_usage(p)
            # warn if < 100 MB free
            if usage.free < 100 * 1024 * 1024:
                print(
                    f"    → Warning: low free space ({usage.free // (1024 * 1024)} MB)."
                )
        except Exception:
            pass


def run_diagnostics() -> None:
    """Print diagnostics about env-only config and resolved directories (with permission checks)."""
    base = ensure_dirs()  # absolute, ensured dirs (from FIT_CONVERTER_* env)
    cfg = effective_config(log=False)  # merged defaults + env, with resolved leaves

    print("🔧 FIT Converter — Diagnostics (env-only)\n")

    # Environment summary (only keys we care about)
    interesting_env = [
        "FIT_CONVERTER_DATA_DIR",
        "FIT_CONVERTER_STATE_DIR",
        "FIT_CONVERTER_INBOX",
        "FIT_CONVERTER_OUTBOX",
        "FIT_CONVERTER_LOGS_DIR",
        "FIT_CONVERTER_TRANSFORM",
        "FIT_CONVERTER_POLL_INTERVAL",
        "FIT_CONVERTER_RETRIES",
        "FIT_CONVERTER_LOG_LEVEL",
        "FIT_CONVERTER_LOG_TO_FILE",
        "FIT_CONVERTER_LOG_ROTATE_MAX_BYTES",
        "FIT_CONVERTER_LOG_BACKUP_COUNT",
        "FIT_CONVERTER_LOG_FILENAME",
        "FLASK_HOST",
        "FLASK_PORT",
        "FLASK_DEBUG",
    ]
    print("Environment variables (set values shown):")
    for key in interesting_env:
        val = os.environ.get(key)
        mark = "✅" if val is not None else "—"
        shown = val if val is not None else ""
        print(f"  {key:<33} {mark} {shown}")

    # Paths + permission checks
    print("\nResolved locations (rwx checks):")
    _check_dir("config_dir", base.config_dir, want_write=True)
    _check_dir("data_dir", base.data_dir, want_write=True, check_space=True)
    _check_dir("state_dir", base.state_dir, want_write=True, check_space=True)
    _check_dir("inbox", base.inbox, want_write=True)
    _check_dir("outbox", base.outbox, want_write=True)
    _check_dir("logs_dir", base.logs_dir, want_write=True)

    # Logging summary
    log_cfg = cfg.get("logging", {})
    log_file = Path(cfg["logs_dir"]) / log_cfg.get("filename", "fit-converter.log")
    print("\nLogging:")
    print(f"  level          : {log_cfg.get('level', 'INFO')}")
    print(f"  to_file        : {log_cfg.get('to_file', True)}")
    print(f"  rotate_max     : {log_cfg.get('rotate_max_bytes', 1_000_000)}")
    print(f"  backup_count   : {log_cfg.get('backup_count', 5)}")
    print(f"  file           : {log_file}")

    # Effective top-level config (brief)
    print("\nEffective config (top-level):")
    for k in ("inbox", "outbox", "logs_dir", "transform", "poll_interval", "retries"):
        v = cfg.get(k)
        print(f"  {k:<14} = {v}")


def main() -> None:
    run_diagnostics()


if __name__ == "__main__":
    main()
