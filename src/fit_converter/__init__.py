# src/fit_converter/__init__.py
from __future__ import annotations

# Re-export the canonical config accessor (no logging here)
from .cfg import effective_config

# Re-export the clean paths API
from .paths import INBOX, LOGS_DIR, OUTBOX, Paths, resolve

__all__ = [
    "effective_config",
    "INBOX",
    "OUTBOX",
    "LOGS_DIR",
    "resolve",
    "Paths",
]
