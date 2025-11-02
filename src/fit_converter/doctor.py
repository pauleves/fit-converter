# src/fit_converter/doctor.py
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Tuple

from fit_converter.cfg import load_config
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
    """Print diagnostics about config and directory resolution, with permission checks."""
    base = ensure_dirs()
    cfg = load_config()

    print("🔧 FIT-Converter Diagnostics\n")

    # Config files
    print("Config directories and files:")
    print(f"  config_dir : {base.config_dir}")
    for fname in ("config.toml", "config.local.toml"):
        path = base.config_dir / fname
        print(f"    - {fname:<18} {'✅ found' if path.exists() else '❌ missing'}")

    # Paths + permission checks
    print("\nData & state locations (rwx checks):")
    _check_dir("data_dir", base.data_dir, want_write=True, check_space=True)
    _check_dir("state_dir", base.state_dir, want_write=True, check_space=True)
    _check_dir("inbox", base.inbox, want_write=True)
    _check_dir("outbox", base.outbox, want_write=True)
    _check_dir("logs_dir", base.logs_dir, want_write=True)
    print(f"\nLog file: {base.logs_dir / 'fit-converter.log'}")

    # Effective config (flattened, brief)
    print("\nEffective config values:")
    for k, v in sorted(cfg.items()):
        if isinstance(v, dict):
            continue
        print(f"  {k:<12} = {v}")


def main() -> None:
    run_diagnostics()


if __name__ == "__main__":
    main()
