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
  2. ./config.toml
  3. ./config.local.toml
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
    "inbox": "inbox",
    "outbox": "outbox",
    "logs_dir": "logs",
    "transform": True,
    "poll_interval": 0.5,
    "retries": 3,
    "logging": {
        "level": "INFO",
        "to_file": True,
        "file_path": None,  # will be derived if missing
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


def _postprocess_effective(cfg: dict) -> dict:
    log_cfg = cfg.get("logging", {})
    if not log_cfg.get("file_path"):
        from pathlib import Path

        log_cfg["file_path"] = str(
            Path(cfg.get("logs_dir", "logs")) / "fit-converter.log"
        )
    cfg["logging"] = log_cfg
    return cfg


def _finalize_logging(cfg: Dict[str, Any]) -> None:
    """Ensure logging.file_path is set, deriving from logs_dir if missing/None."""
    log = cfg.get("logging") or {}
    if log.get("file_path") in (None, ""):
        logs_dir = cfg.get("logs_dir", "logs")
        log["file_path"] = str(Path(logs_dir) / "fit-converter.log")
    cfg["logging"] = log


# ----------------------------
# Public API
# ----------------------------


def load_config() -> Dict[str, Any]:
    """
    Build the merged configuration dict WITHOUT logging.

    Order of application:
      defaults → config.toml → config.local.toml → env (FIT_CONVERTER_*)
    """
    cfg: Dict[str, Any] = _DEFAULTS.copy()

    # 2) Global config file or fallback of example file.
    main = Path("config.toml")
    example = Path("config.example.toml")
    if main.exists():
        cfg.update(_load_toml(main))
    elif example.exists():
        cfg.update(_load_toml(example))

    # 3) Local developer overrides (ignored if absent)
    cfg.update(_load_toml(Path("config.local.toml")))

    # 4) Environment overrides (FIT_CONVERTER_*)
    for key, value in os.environ.items():
        if not key.startswith("FIT_CONVERTER_"):
            continue
        name = key.removeprefix("FIT_CONVERTER_").lower()
        # If the key is unknown to defaults, leave as string (opt-in behaviour)
        # Otherwise coerce to the default's type.
        ref = _DEFAULTS.get(name)
        cfg[name] = _coerce_type(value, ref) if name in _DEFAULTS else value

    return cfg


def effective_config(*, log: bool = True) -> Dict[str, Any]:
    """
    Return the final merged config and (optionally) log it at INFO level.
    Callers may apply CLI-flag overrides on top of this result.
    """
    cfg = load_config()
    _finalize_logging(cfg)
    if log:
        logger = logging.getLogger(__name__)
        logger.info("[cfg] Effective configuration:")
        # Align keys in a stable order for readability
        for k in sorted(cfg.keys()):
            logger.info("  %-14s = %s", k, cfg[k])

    return cfg
