# src/fit_converter/cfg.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict

"""
Minimal configuration for fit-converter.

Model:
  - Start from in-code defaults.
  - Override with environment variables.
    * Supported prefixes (checked in this order):
        1) FIT_CONVERTER_
    * Examples:
        FIT_CONVERTER_TRANSFORM=false
        FIT_CONVERTER_LOG_LEVEL=DEBUG

Notes:
  - Types are coerced based on the default (bool/int/float → parsed; else str).
  - Paths (inbox/outbox/logs_dir/data_dir) are normalized via fit_converter.paths.resolve
    in effective_config().
"""

__all__ = ["effective_config", "load_config"]

# ----------------------------
# Defaults
# ----------------------------

_DEFAULTS: Dict[str, Any] = {
    "data_dir": None,  # Optional override; resolver provides platform default
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
        "filename": "fit-converter.log",
    },
}

# Only allow env overrides for flat leaf keys; roots are owned by paths.py
_FLAT_KEYS = {
    k for k in _DEFAULTS.keys() if k not in ("logging", "data_dir", "state_dir")
}

# Logging subkeys allowed via env (e.g., FIT_CONVERTER_LOG_LEVEL=DEBUG)
_LOG_KEYS = {"level", "to_file", "rotate_max_bytes", "backup_count", "filename"}

# Env prefixes checked in order (first match wins)
_PREFIXES = ("FIT_CONVERTER_",)


# ----------------------------
# Helpers
# ----------------------------


def _coerce(value: str, reference: Any) -> Any:
    if isinstance(reference, bool):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(reference, int):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _get_env(name: str) -> str | None:
    """Return the first env value found across supported prefixes, else None."""
    for prefix in _PREFIXES:
        key = f"{prefix}{name}"
        if key in os.environ:
            return os.environ[key]
    return None


# ----------------------------
# Public API
# ----------------------------


def load_config() -> Dict[str, Any]:
    """
    Build the merged configuration dict (defaults + env overrides only).
    """
    cfg: Dict[str, Any] = {**_DEFAULTS, "logging": dict(_DEFAULTS["logging"])}

    # Top-level overrides
    for name in _FLAT_KEYS:
        env_val = _get_env(name.upper())
        if env_val is not None:
            cfg[name] = _coerce(env_val, _DEFAULTS[name])

    # Logging overrides (LOG_LEVEL / LOG_TO_FILE / LOG_ROTATE_MAX_BYTES / LOG_BACKUP_COUNT)
    for k in _LOG_KEYS:
        env_val = _get_env(f"LOG_{k.upper()}")
        if env_val is not None:
            cfg["logging"][k] = _coerce(env_val, _DEFAULTS["logging"][k])

    return cfg


def effective_config(*, log: bool = True) -> Dict[str, Any]:
    """
    Return the final merged config and (optionally) log it.
    Also resolves inbox/outbox/logs_dir to absolute paths (CWD-independent).
    """
    cfg = load_config()

    # Normalize paths using the existing resolver
    from fit_converter.paths import (  # local import to avoid cycles
        resolve as resolve_paths,
    )

    # Let paths.py determine base roots from env; only pass leaf overrides
    p = resolve_paths(
        {
            "inbox": cfg.get("inbox"),
            "outbox": cfg.get("outbox"),
            "logs_dir": cfg.get("logs_dir"),
        }
    )

    # Reflect effective absolute paths back into cfg (as strings)
    cfg["inbox"] = str(p.inbox)
    cfg["outbox"] = str(p.outbox)
    cfg["logs_dir"] = str(p.logs_dir)

    if log:
        logger = logging.getLogger(__name__)
        logger.info("[cfg] Effective configuration:")
        for k in sorted(cfg.keys()):
            logger.info("  %-14s = %s", k, cfg[k])

    return cfg
