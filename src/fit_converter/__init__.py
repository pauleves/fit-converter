# fit_converter/__init__.py
from pathlib import Path

from .config_load import load_config
from .logging_setup import configure_logging
from .paths import resolve_paths

# --- Load config and set up paths ---
cfg = load_config()
paths = resolve_paths(cfg)

# --- Configure global logging once ---
log_cfg = cfg.get("logging", {})
default_log = Path("logs") / "fit-converter.log"
log_file = Path(log_cfg.get("file_path") or default_log)

configure_logging(
    level=log_cfg.get("level", "INFO"),
    to_file=log_cfg.get("to_file", True),
    file_path=str(log_file),
    rotate_max_bytes=log_cfg.get("rotate_max_bytes", 1_000_000),
    backup_count=log_cfg.get("backup_count", 5),
)

# Export convenience handles
__all__ = ["cfg", "paths"]
