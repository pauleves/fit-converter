# src/fit_converter/paths.py
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

APP_PKG_NAME = "fit_converter"  # import/package name
# Env overrides (keep names short & explicit)
ENV_CONFIG_DIR = "APP_CONFIG_DIR"
ENV_DATA_DIR = "APP_DATA_DIR"
ENV_STATE_DIR = "APP_STATE_DIR"
ENV_LOGS_DIR = "APP_LOGS_DIR"  # optional: force logs dir (e.g., /var/log/fit_converter)


def _expand(p: str | Path) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(p)))).resolve()


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _default_config_dir() -> Path:
    if _is_windows():
        base = (
            os.environ.get("APPDATA")
            or os.environ.get("LOCALAPPDATA")
            or (Path.home() / "AppData" / "Roaming")
        )
        return _expand(Path(base) / APP_PKG_NAME)
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return _expand(Path(xdg_config) / APP_PKG_NAME)


def _default_data_dir() -> Path:
    if _is_windows():
        base = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or (Path.home() / "AppData" / "Local")
        )
        return _expand(Path(base) / APP_PKG_NAME)
    xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return _expand(Path(xdg_data) / APP_PKG_NAME)


def _default_state_dir() -> Path:
    if _is_windows():
        base = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or (Path.home() / "AppData" / "Local")
        )
        # State root for the app (logs will be under a Logs/ subfolder later)
        return _expand(Path(base) / APP_PKG_NAME)
    xdg_state = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    return _expand(Path(xdg_state) / APP_PKG_NAME)


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    data_dir: Path
    state_dir: Path
    inbox: Path
    outbox: Path
    logs_dir: Path


@lru_cache(maxsize=1)
def resolve_runtime_paths() -> Paths:
    """Absolute, stable paths — never depends on CWD."""
    config_dir = (
        _expand(os.environ[ENV_CONFIG_DIR])
        if os.environ.get(ENV_CONFIG_DIR)
        else _default_config_dir()
    )
    data_dir = (
        _expand(os.environ[ENV_DATA_DIR])
        if os.environ.get(ENV_DATA_DIR)
        else _default_data_dir()
    )
    state_dir = (
        _expand(os.environ[ENV_STATE_DIR])
        if os.environ.get(ENV_STATE_DIR)
        else _default_state_dir()
    )

    # User-facing data
    inbox = data_dir / "inbox"
    outbox = data_dir / "outbox"

    # Operational state: logs directory lives under state_dir by default
    logs_dir = (
        _expand(os.environ[ENV_LOGS_DIR])
        if os.environ.get(ENV_LOGS_DIR)
        else ((state_dir / "Logs") if _is_windows() else (state_dir / "logs"))
    )

    return Paths(
        config_dir=config_dir,
        data_dir=data_dir,
        state_dir=state_dir,
        inbox=inbox,
        outbox=outbox,
        logs_dir=logs_dir,
    )


def ensure_dirs(p: Paths | None = None) -> Paths:
    paths = p or resolve_runtime_paths()
    # Create directories (permissions tightened later if you want)
    for d in (
        paths.config_dir,
        paths.data_dir,
        paths.state_dir,
        paths.inbox,
        paths.outbox,
        paths.logs_dir,
    ):
        d.mkdir(parents=True, exist_ok=True, mode=0o755)
    return paths


def _resolve_leaf(base: Path, value: str | Path | None, default_sub: str) -> Path:
    """
    Resolve a leaf directory relative to a given base (data_dir or state_dir),
    expanding ~ and env vars, never using CWD.
    """
    if not value:
        p = base / default_sub
    else:
        p = Path(os.path.expanduser(os.path.expandvars(str(value))))
        p = p if p.is_absolute() else (base / p)
    p.mkdir(parents=True, exist_ok=True, mode=0o755)
    return p


def resolve(cfg: Mapping[str, Any] | None = None) -> Paths:
    """
    Compute Paths using the environment/platform defaults established by
    resolve_runtime_paths(). If a cfg mapping is provided,
    only the keys 'inbox', 'outbox', 'logs_dir' are used to override leaf dirs.
    resolve_runtime_paths().
    If a cfg mapping is provided, you may pass 'data_dir' and/or 'state_dir' to
    override the base roots, plus 'inbox'/'outbox'/'logs_dir' for leaves.
    """
    base = ensure_dirs()  # config_dir, data_dir, state_dir already set & created

    cfg = cfg or {}
    # Allow overriding of the base roots via cfg
    data_root_v = cfg.get("data_dir")
    state_root_v = cfg.get("state_dir")

    def _expand_abs_or_join(root: Path, val: str | Path | None) -> Path:
        if not val:
            return root
        p = Path(os.path.expanduser(os.path.expandvars(str(val))))
        return p if p.is_absolute() else (root / p)

    data_root = _expand_abs_or_join(base.data_dir, data_root_v)
    state_root = _expand_abs_or_join(base.state_dir, state_root_v)
    data_root.mkdir(parents=True, exist_ok=True, mode=0o755)
    state_root.mkdir(parents=True, exist_ok=True, mode=0o755)

    inbox_v = cfg.get("inbox")
    outbox_v = cfg.get("outbox")
    logs_v = cfg.get("logs_dir")

    inbox = _resolve_leaf(data_root, inbox_v, "inbox")
    outbox = _resolve_leaf(data_root, outbox_v, "outbox")
    logsdir = _resolve_leaf(state_root, logs_v, "logs")  # logs live under state

    return Paths(
        config_dir=base.config_dir,
        data_dir=data_root,
        state_dir=state_root,
        inbox=inbox,
        outbox=outbox,
        logs_dir=logsdir,
    )
