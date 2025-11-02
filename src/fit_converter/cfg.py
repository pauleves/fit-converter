# src/fit_converter/cfg.py
from __future__ import annotations

import logging
import os
import tomllib
from pathlib import Path
from typing import Any, Dict

"""
Layered runtime configuration for fit-converter.

Precedence (low → high):
  1. Built-in defaults
  2. <config_dir>/config.toml
  3. <config_dir>/config.local.toml
  4. Environment variables (FIT_CONVERTER_*)
  5. (Caller applies CLI flag overrides after calling effective_config())

Usage:
    from fit_converter.cfg import effective_config
    config = effective_config(log=True)  # dict

Environment variables:
    Prefix: FIT_CONVERTER_
    Example: FIT_CONVERTER_OUTBOX=/tmp/out  → {"outbox": "/tmp/out"}

Notes:
    - Types for env vars are coerced based on the default value for that key.
      (bool/int/float supported; otherwise str)
"""


__all__ = [
    "effective_config",
    "load_config",
]

# ----------------------------
# Defaults
# ----------------------------

_DEFAULTS: Dict[str, Any] = {
    "data_dir": None,  # optional override; resolver has platform default
    "inbox": "inbox",
    "outbox": "outbox",
    "logs_dir": "logs",
    "transform": True,
    "poll_interval": 0.5,
    "retries": 3,
    "logging": {
        "level": "INFO",
        "to_file": True,
        "rotate_max_bytes": 1_000_000,
        "backup_count": 5,
    },
}


# ----------------------------
# Helpers
# ----------------------------


def _load_toml(path: Path) -> Dict[str, Any]:
    """
    Load TOML file into a flat dict. Returns {} if the path does not exist.
    """
    if not path.exists():
        return {}
    with path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            logging.getLogger(__name__).warning("Malformed TOML %s: %s", path, e)
            return {}
    return dict(data)


def _coerce_type(value: str, reference: Any) -> Any:
    """
    Coerce string 'value' coming from the environment to the type of 'reference'
    (derived from _DEFAULTS). Supports bool/int/float, falls back to str.
    """
    if isinstance(reference, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(reference, int):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


# ----------------------------
# Public API
# ----------------------------


def load_config() -> Dict[str, Any]:
    """
    Build the merged configuration dict WITHOUT logging.
    Order: defaults → config.toml → config.local.toml → env (FIT_CONVERTER_*)
    Config files are read from the resolved config_dir (never CWD).
    """
    from fit_converter.paths import (  # local import avoids any risk of cycles
        resolve_runtime_paths,
    )

    cfg: Dict[str, Any] = _DEFAULTS.copy()

    base = resolve_runtime_paths()
    main = base.config_dir / "config.toml"
    local = base.config_dir / "config.local.toml"

    cfg.update(_load_toml(main))
    cfg.update(_load_toml(local))

    # If user prefers a [paths] table, merge its keys into the flat namespace.
    # Supported keys: data_dir, inbox, outbox, logs_dir
    paths_tbl = cfg.pop("paths", {}) or {}
    for k in ("data_dir", "inbox", "outbox", "logs_dir"):
        if k in paths_tbl:
            cfg[k] = paths_tbl[k]

    # Environment overrides (FIT_CONVERTER_*)
    for key, value in os.environ.items():
        if not key.startswith("FIT_CONVERTER_"):
            continue
        name = key.removeprefix("FIT_CONVERTER_").lower()
        ref = _DEFAULTS.get(name)
        cfg[name] = _coerce_type(value, ref) if name in _DEFAULTS else value

    return cfg


def effective_config(*, log: bool = True) -> Dict[str, Any]:
    """
    Return the final merged config and (optionally) log it.
    Also resolves inbox/outbox/logs_dir to absolute paths (CWD-independent).
    """
    cfg = load_config()

    # Run through the path resolver to normalise relative values against data/state.
    from fit_converter.paths import resolve as resolve_paths

    p = resolve_paths(
        {
            "data_dir": cfg.get("data_dir"),
            "state_dir": cfg.get("state_dir"),
            "inbox": cfg.get("inbox"),
            "outbox": cfg.get("outbox"),
            "logs_dir": cfg.get("logs_dir"),
        }
    )

    # Reflect effective absolute paths back into cfg
    cfg["inbox"] = str(p.inbox)
    cfg["outbox"] = str(p.outbox)
    cfg["logs_dir"] = str(p.logs_dir)

    if log:
        logger = logging.getLogger(__name__)
        logger.info("[cfg] Effective configuration:")
        for k in sorted(cfg.keys()):
            logger.info("  %-14s = %s", k, cfg[k])

    return cfg
