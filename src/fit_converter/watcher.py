from __future__ import annotations

import argparse
import logging
import queue
import signal
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from fit_converter.cfg import effective_config
from fit_converter.logging_setup import configure_logging  # if not already present
from fit_converter.paths import INBOX, OUTBOX, resolve

from .converter import fit_to_csv

logger = logging.getLogger(__name__)

# Directories (overridable via CLI)
inbox: Path = INBOX
outbox: Path = OUTBOX

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
    rows = fit_to_csv(in_path, out_path, transform=transform)
    logger.info("[watcher] Done: %s rows → %s", rows, out_path)


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
        except Exception:
            logger.exception(
                "[watcher] Error converting %s (attempt %d/%d)",
                in_path.name,
                attempt,
                retries,
            )
            time.sleep(1.0)
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

    parser = argparse.ArgumentParser(
        prog="fit-converter-watcher", description="Watch inbox/ and convert FIT→CSV"
    )
    # CLI only overrides when provided; config supplies defaults
    parser.add_argument(
        "--inbox",
        type=Path,
        default=None,
        help="Directory to watch for .fit files (default from config)",
    )
    parser.add_argument(
        "--outbox",
        type=Path,
        default=None,
        help="Directory to write CSVs (default from config)",
    )
    parser.add_argument(
        "--transform",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Apply readability transforms (default from config)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=None,
        help="Polling interval while stabilising a file (seconds; default from config)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Retries per file on failure (default from config)",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        default=None,
        help="Override log level for this process",
    )
    args = parser.parse_args()

    # 1) Base config (no log spam yet)
    cfg = effective_config(log=False)

    # 2) Merge CLI overrides only if provided
    merged = dict(cfg)
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
        merged["log_level"] = args.log_level

    # 3) Configure logging using the final level
    configure_logging(level=merged.get("log_level", "INFO"))

    # 4) Compute ensured paths + runtime knobs from merged config
    p = resolve(merged)
    inbox, outbox = p.inbox, p.outbox
    TRANSFORM = bool(merged.get("transform", True))
    POLL = float(merged.get("poll_interval", 0.5))
    RETRIES = int(merged.get("retries", 3))

    # 5) Start worker + observer
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


if __name__ == "__main__":
    main()
