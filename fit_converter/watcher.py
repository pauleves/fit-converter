from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from fit_converter import paths

from .converter import fit_to_csv

logger = logging.getLogger(__name__)
inbox = paths["inbox"]
outbox = paths["outbox"]


# --- tiny helper: wait until a file is "stable" (size unchanged for N checks) ---
def wait_until_stable(path: Path, timeout_s=30, poll_s=0.5) -> bool:
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
_tasks: "queue.Queue[Path]" = queue.Queue()


def worker():
    while True:
        path = _tasks.get()
        if path is None:
            break
        try:
            process_fit(path)
        except Exception as e:
            logger.exception(
                f"[watcher] ERROR converting {path.name}: {e}", file=sys.stderr
            )
        finally:
            _tasks.task_done()


def process_fit(in_path: Path):
    if not in_path.exists():
        logger.warning(f"[watcher] Skipped (missing): {in_path}")
        return
    if in_path.suffix.lower() != ".fit":
        logger.warning(f"[watcher] Ignored (not .fit): {in_path.name}")
        return

    # Wait for file to finish writing
    if not wait_until_stable(in_path):
        logger.warning(
            f"[watcher] WARNING: {in_path.name} did not stabilize; attempting anyway."
        )

    out_name = in_path.name + ".csv"
    out_path = outbox / out_name

    logger.info(f"[watcher] Converting → {out_path.name}")
    rows = fit_to_csv(in_path, out_path, transform=True)
    logger.info(f"[watcher] Done: {rows} rows → {out_path}")


class InboxHandler(FileSystemEventHandler):
    def on_created(self, event: FileSystemEvent):
        self._handle(event)

    def on_moved(self, event: FileSystemEvent):
        # moved events have .dest_path
        self._handle(event, moved=True)

    def on_modified(self, event: FileSystemEvent):
        # some tools write in-place; treat as candidate but debounce will protect us
        self._handle(event)

    def _handle(self, event: FileSystemEvent, moved: bool = False):
        if event.is_directory:
            return
        path_str = getattr(event, "dest_path", None) if moved else event.src_path
        path = Path(path_str)
        if path.suffix.lower() != ".fit":
            return
        # enqueue work (worker will debounce/convert)
        _tasks.put(path)


def main():

    # start worker
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # start observer
    observer = Observer()
    handler = InboxHandler()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    logger.info(f"[watcher] Watching: {inbox}  →  writing CSVs to: {inbox}")
    logger.info("[watcher] Drop .fit files into inbox/ to convert (Ctrl+C to stop).")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("\n[watcher] Stopping…")
    finally:
        observer.stop()
        observer.join()
        _tasks.put(None)  # stop worker
        _tasks.join()


if __name__ == "__main__":
    main()
