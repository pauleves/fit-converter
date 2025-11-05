from __future__ import annotations

import argparse
import logging
import queue
import signal
import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from . import __version__
from .cfg import effective_config
from .converter import ConversionError, convert_with_report
from .logging_setup import configure_logging, get_logger
from .paths import resolve

logger = logging.getLogger(__name__)


# Directories (set in main() after config/logging)
inbox: Path
outbox: Path

# Runtime controls (overridable via CLI)
_STOP = False
_PENDING: set[Path] = set()
_LAST_ENQUEUED: dict[Path, float] = {}
RETRIES: int = 3
POLL: float = 0.5
TRANSFORM: bool = True
DEBOUNCE_S: float = 2.0  # ignore repeat events within 2s


# --- tiny helper: wait until a file is "stable" (size unchanged for N checks) ---
def wait_until_stable(path: Path, timeout_s: float = 30.0, poll_s: float = 0.5) -> bool:
    logger.debug("Waiting for file to stabilize: %s", path)
    deadline = time.time() + timeout_s
    last_size = -1
    while time.time() < deadline:
        size = path.stat().st_size
        if size == last_size:
            logger.debug("File stabilized: %s", path)
            return True
        last_size = size
        time.sleep(poll_s)
    logger.warning("File did not stabilize within %ss: %s", timeout_s, path)
    return False


# --- worker thread to serialize conversions (simple backpressure) ---
_tasks: "queue.Queue[Path | None]" = queue.Queue()


def worker() -> None:
    while True:
        path = _tasks.get()
        if path is None:
            _tasks.task_done()
            break
        try:
            process_fit_with_retries(
                path, retries=RETRIES, transform=TRANSFORM, poll_s=POLL
            )
        except Exception:
            logger.exception(
                "[watcher] Unhandled error converting %s", getattr(path, "name", path)
            )
        finally:
            _PENDING.discard(path)
            _tasks.task_done()


def process_fit(in_path: Path, *, transform: bool = True, poll_s: float = POLL) -> None:
    if not in_path.exists():
        logger.warning("[watcher] Skipped (missing): %s", in_path)
        return
    if in_path.suffix.lower() != ".fit":
        logger.warning("[watcher] Ignored (not .fit): %s", in_path.name)
        return

    # Wait for file to finish writing
    if not wait_until_stable(in_path, poll_s=poll_s):
        logger.warning(
            "[watcher] WARNING: %s did not stabilize; attempting anyway.", in_path.name
        )

    out_name = in_path.stem + ".csv"  # e.g., "activity.fit" -> "activity.csv"
    out_path = outbox / out_name

    logger.info("[watcher] Converting → %s", out_path.name)
    report = convert_with_report(
        in_path,
        out_path,
        transform=transform,
        logger=logger,
    )

    if report.ok:
        logger.debug("[watcher] Done: %s rows → %s", report.rows, out_path)
    else:
        logger.debug("[watcher] Failed: %s", report.message)


def process_fit_with_retries(
    in_path: Path,
    *,
    retries: int = 3,
    transform: bool = True,
    poll_s: float = POLL,
) -> None:
    for attempt in range(1, retries + 1):
        try:
            process_fit(in_path, transform=transform, poll_s=poll_s)
            return
        except ConversionError as e:
            # Expected user/data error (e.g., corrupt FIT): don't retry
            logger.warning(
                "[watcher] No-retry conversion failure for %s: %s",
                in_path.name,
                e,
            )
            break
        except Exception:
            logger.exception(
                "[watcher] Error converting %s (attempt %d/%d)",
                in_path.name,
                attempt,
                retries,
            )
            # light backoff before retrying unexpected/system errors
            time.sleep(min(1.0, 0.25 * attempt))
    logger.error(
        "[watcher] Permanent failure after %d attempts: %s", retries, in_path.name
    )


class InboxHandler(FileSystemEventHandler):
    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        self._handle(event, moved=True)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent, moved: bool = False) -> None:
        if event.is_directory:
            return
        path_str = getattr(event, "dest_path", None) if moved else event.src_path
        path = Path(path_str)
        if path.suffix.lower() != ".fit":
            return

        # De-dupe if already queued/processing
        if path in _PENDING:
            logger.debug(
                "[watcher] Skipping duplicate enqueue: %s (already pending)", path.name
            )
            return

        # Debounce rapid-fire events
        now = time.monotonic()
        last = _LAST_ENQUEUED.get(path, 0.0)
        if now - last < DEBOUNCE_S:
            logger.debug(
                "[watcher] Debounced event for %s (%.2fs < %.2fs)",
                path.name,
                now - last,
                DEBOUNCE_S,
            )
            return

        _LAST_ENQUEUED[path] = now
        _PENDING.add(path)
        _tasks.put(path)
        logger.debug("[watcher] Enqueued: %s", path.name)


def _sigterm(*_: object) -> None:
    global _STOP
    _STOP = True
    logger.info("[watcher] Shutdown requested…")


def main() -> None:
    """
    CLI entry point. Adds flags but keeps the existing observer/queue design intact.
    """
    global inbox, outbox, RETRIES, POLL, TRANSFORM

    parser = build_parser()
    args = parser.parse_args()

    # 1) Load base config once (no logging yet)
    cfg = effective_config(log=False)

    # 2) Merge CLI overrides only if provided
    merged = dict(cfg)
    merged["logging"] = dict(cfg.get("logging", {}))  # make a shallow copy

    if args.inbox is not None:
        merged["inbox"] = args.inbox
    if args.outbox is not None:
        merged["outbox"] = args.outbox
    if args.retries is not None:
        merged["retries"] = args.retries
    if args.poll is not None:
        merged["poll_interval"] = args.poll
    if args.transform is not None:
        merged["transform"] = bool(args.transform)
    if args.log_level is not None:
        # CLI wins for this process
        merged["logging"]["level"] = args.log_level

    # 3) Compute ensured paths from merged config (roots come from env; only pass leaves)
    p = resolve(
        {
            "inbox": merged.get("inbox"),
            "outbox": merged.get("outbox"),
            "logs_dir": merged.get("logs_dir"),
        }
    )

    # 4) Configure logging once, using resolved logs_dir and unified logging config
    configure_logging(logs_dir=p.logs_dir, logging_cfg=merged["logging"])
    global logger
    logger = get_logger("fit_converter.watcher")
    # Optional: cap noisy libs to avoid inotify spam at DEBUG
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    inbox, outbox = p.inbox, p.outbox
    TRANSFORM = bool(merged.get("transform", True))
    POLL = float(merged.get("poll_interval", 0.5))
    RETRIES = int(merged.get("retries", 3))

    # 5) Start worker + observer
    _banner_watcher(merged, logger)
    if args.log_level == "DEBUG":
        # Show additional logger info
        _logging_diag(logger)
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    observer = Observer()
    handler = InboxHandler()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()
    logger.info("[watcher] Watching: %s  →  writing CSVs to: %s", inbox, outbox)
    logger.info(
        "[watcher] Poll=%.3fs  Retries=%d  Transform=%s", POLL, RETRIES, TRANSFORM
    )
    logger.info("[watcher] Drop .fit files into inbox/ to convert (Ctrl+C to stop).")

    # 6) Handle SIGTERM (systemd/Docker) and Ctrl+C
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    try:
        while not _STOP:
            time.sleep(1.0)
    finally:
        observer.stop()
        observer.join()
        _tasks.put(None)  # stop worker
        _tasks.join()
        logger.info("[watcher] Stopped.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fit-converter-watcher",
        description="Watch inbox/ and convert FIT→CSV",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Use config-defined inbox/outbox and defaults\n"
            "  fit-converter-watcher\n\n"
            "  # Override paths\n"
            "  fit-converter-watcher --inbox ./inbox --outbox ./outbox\n\n"
            "  # Tweak stability polling and retries\n"
            "  fit-converter-watcher --poll 0.5 --retries 2\n\n"
            "  # Force transforms on (overrides config for this run)\n"
            "  fit-converter-watcher --transform\n"
        ),
    )

    # Paths
    g_paths = parser.add_argument_group("Paths")
    g_paths.add_argument(
        "--inbox",
        type=Path,
        default=None,
        help="Directory to watch for .fit files (default from config)",
    )
    g_paths.add_argument(
        "--outbox",
        type=Path,
        default=None,
        help="Directory to write CSVs (default from config)",
    )

    # Behavior
    g_beh = parser.add_argument_group("Behavior")
    g_beh.add_argument(
        "--transform",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Apply readability transforms (default from config)",
    )
    g_beh.add_argument(
        "--poll",
        type=float,
        default=None,
        help="Polling interval while stabilising a file (seconds; default from config)",
    )

    # Reliability & Logging
    g_rel = parser.add_argument_group("Reliability & Logging")
    g_rel.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Retries per file on failure (default from config)",
    )
    g_rel.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default=None,
        help="Override log level for this process",
    ),
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def _banner_watcher(cfg, logger):
    """Log runtime settings for the watcher process."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info("┌─ FIT→CSV — Watcher")
    logger.info("│ time: %s", now)
    logger.info("│ inbox: %s", cfg.get('inbox'))
    logger.info("│ outbox: %s", cfg.get('outbox'))
    logger.info("│ poll_interval: %ss", cfg.get('poll_interval', 0.5))
    logger.info("│ retries: %s", cfg.get('retries', 3))
    logger.info("│ transform: %s", cfg.get('transform', True))
    logger.info("│ log-level: %s", cfg.get('logging', {}).get('level', 'INFO'))
    cfg_path = cfg.get('config_path')
    if cfg_path:
        logger.info("│ config: %s", cfg_path)
    logger.info("└────────────────────")


def _logging_diag(logger):
    logger.info("┌─ logging diag for %s", logger.name)
    logger.info("│ logger.level: %s", logging.getLevelName(logger.level))
    root = logging.getLogger()
    logger.info("│ root.level: %s", logging.getLevelName(root.level))
    logger.info("│ root.handlers: %d", len(root.handlers))
    for i, h in enumerate(root.handlers):
        h_cls = type(h).__name__
        h_lvl = logging.getLevelName(getattr(h, "level", logging.NOTSET))
        dest = getattr(h, "baseFilename", None) or getattr(h, "stream", None)
        logger.info("│  #%d %s level=%s dest=%s", i, h_cls, h_lvl, dest)
    logger.info("└────────────")


if __name__ == "__main__":
    main()
