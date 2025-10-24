# src/fit_converter/paths.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from fit_converter.cfg import effective_config  # no logging here to avoid loops


@dataclass(frozen=True)
class Paths:
    inbox: Path
    outbox: Path
    logs_dir: Path


def _resolve_dir(p: str | Path) -> Path:
    p = Path(p).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve(cfg: Mapping[str, Any] | None = None) -> Paths:
    """
    Compute paths from a provided config mapping (or current effective config if None).
    Creates directories if missing. Returns immutable Paths.
    """
    c = dict(effective_config(log=False) if cfg is None else cfg)
    inbox = _resolve_dir(c.get("inbox", "inbox"))
    outbox = _resolve_dir(c.get("outbox", "outbox"))
    logs_dir = _resolve_dir(c.get("logs_dir", "logs"))
    return Paths(inbox=inbox, outbox=outbox, logs_dir=logs_dir)


# Module-level convenience based on current effective config
_DEFAULT = resolve()
INBOX: Path = _DEFAULT.inbox
OUTBOX: Path = _DEFAULT.outbox
LOGS_DIR: Path = _DEFAULT.logs_dir
