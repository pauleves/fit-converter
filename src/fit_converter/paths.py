# fit_converter/paths.py
from pathlib import Path


def resolve_paths(cfg: dict) -> dict:
    paths_cfg = (cfg or {}).get("paths", {})
    inbox = Path(paths_cfg.get("inbox", "inbox")).expanduser()
    outbox = Path(paths_cfg.get("outbox", "outbox")).expanduser()

    # Resolve relative paths against current working directory
    inbox = (Path.cwd() / inbox) if not inbox.is_absolute() else inbox
    outbox = (Path.cwd() / outbox) if not outbox.is_absolute() else outbox

    inbox.mkdir(parents=True, exist_ok=True)
    outbox.mkdir(parents=True, exist_ok=True)
    return {"inbox": inbox, "outbox": outbox}
