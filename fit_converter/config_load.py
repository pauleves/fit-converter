import os
import tomllib  # Python 3.11+
from pathlib import Path


def load_config(path: str = "config.toml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("rb") as f:
        cfg = tomllib.load(f)
    # env overrides (example for LOG_LEVEL)
    lvl = os.getenv("LOG_LEVEL")
    if lvl:
        cfg.setdefault("logging", {})["level"] = lvl
    return cfg
