from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from time import sleep

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from fit_to_csv import fit_to_csv

BASE_DIR = Path(__file__).parent
INBOX = BASE_DIR / "inbox"
OUTBOX = BASE_DIR / "outbox"


# --- tiny helper: wait until a file is "stable" (size unchanged for N checks) ---
def wait_until_stable(path: Path, checks: int = 5, interval: float = 0.2) -> bool:
    """Return True if file size remains unchanged for `checks` intervals."""
    last = -1
    stable = 0
    for _ in range(checks * 10):  # upper bound so we don't hang forever
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            stable = 0
            sleep(interval)
            continue
        if size == last and size > 0:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last = size
        sleep(interval)
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
            print(f"[watcher] ERROR converting {path.name}: {e}", file=sys.stderr)
        finally:
            _tasks.task_done()


def process_fit(in_path: Path):
    if not in_path.exists():
        print(f"[watcher] Skipped (missing): {in_path}")
        return
    if in_path.suffix.lower() != ".fit":
        print(f"[watcher] Ignored (not .fit): {in_path.name}")
        return

    # Wait for file to finish writing
    if not wait_until_stable(in_path):
        print(
            f"[watcher] WARNING: {in_path.name} did not stabilize; attempting anyway."
        )

    OUTBOX.mkdir(exist_ok=True)
    out_name = in_path.name + ".csv"
    out_path = OUTBOX / out_name

    print(f"[watcher] Converting → {out_path.name}")
    rows = fit_to_csv(in_path, out_path, transform=True)
    print(f"[watcher] Done: {rows} rows → {out_path}")


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
    INBOX.mkdir(exist_ok=True)
    OUTBOX.mkdir(exist_ok=True)

    # start worker
    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # start observer
    observer = Observer()
    handler = InboxHandler()
    observer.schedule(handler, str(INBOX), recursive=False)
    observer.start()

    print(f"[watcher] Watching: {INBOX}  →  writing CSVs to: {OUTBOX}")
    print("[watcher] Drop .fit files into inbox/ to convert (Ctrl+C to stop).")

    try:
        while True:
            sleep(1.0)
    except KeyboardInterrupt:
        print("\n[watcher] Stopping…")
    finally:
        observer.stop()
        observer.join()
        _tasks.put(None)  # stop worker
        _tasks.join()


if __name__ == "__main__":
    main()
