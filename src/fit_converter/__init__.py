# src/fit_converter/__init__.py
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

# Re-export the canonical config accessor (no logging here)
from .cfg import effective_config

# Public runtime version (reads from installed package metadata)
try:
    __version__ = _pkg_version("fit-converter")
except PackageNotFoundError:
    # Falls back when running from source without an installed dist/wheel
    __version__ = "0.0.0+dev"

# Re-export the clean paths API
from .paths import Paths, ensure_dirs, resolve, resolve_runtime_paths

__all__ = [
    "effective_config",
    "Paths",
    "resolve",
    "resolve_runtime_paths",
    "ensure_dirs",
]
