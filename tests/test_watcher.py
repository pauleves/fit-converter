# tests/test_watcher.py
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

import fit_converter.watcher as w
from fit_converter.converter import ConversionError


def _start_worker():
    t = threading.Thread(target=w.worker, daemon=True)
    t.start()
    return t


def _stop_worker(t: threading.Thread | None = None):
    # Only stop if a worker is running; avoid enqueueing a sentinel with no consumer.
    if t is not None and t.is_alive():
        w._tasks.put(None)
        t.join(timeout=2)


@pytest.fixture(autouse=True)
def _isolate_globals(monkeypatch, tmp_path: Path):
    """
    Ensure each test has its own inbox/outbox, queue, and debounce state.
    """
    # Fresh dirs
    inbox = tmp_path / "inbox"
    outbox = tmp_path / "outbox"
    inbox.mkdir()
    outbox.mkdir()

    # Reset watcher globals
    w.inbox = inbox
    w.outbox = outbox
    w.RETRIES = 3
    w.POLL = 0.05
    w.TRANSFORM = True
    w.DEBOUNCE_S = 2.0

    # Fresh queue + state
    from queue import Queue

    monkeypatch.setattr(w, "_tasks", Queue())
    w._PENDING.clear()
    w._LAST_ENQUEUED.clear()

    # No teardown stop here — individual tests manage worker lifecycle
    yield


def test_retry_then_success(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    def fake_convert(in_path: Path, out_path: Path, *, transform: bool = True):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary failure")
        out_path.write_text("csv\n")
        return 1

    monkeypatch.setattr(w, "fit_to_csv", fake_convert)

    f = w.inbox / "run.fit"
    f.write_bytes(b"fakefit")

    t = _start_worker()
    w._tasks.put(f)
    w._tasks.join()
    _stop_worker(t)

    assert (w.outbox / "run.csv").exists()
    assert calls["n"] == 2


def test_conversion_error_no_retry(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    def fake_convert(in_path: Path, out_path: Path, *, transform: bool = True):
        calls["n"] += 1
        raise ConversionError("corrupt FIT")

    monkeypatch.setattr(w, "fit_to_csv", fake_convert)

    f = w.inbox / "bad.fit"
    f.write_bytes(b"xxxx")

    t = _start_worker()
    w._tasks.put(f)
    w._tasks.join()
    _stop_worker(t)

    assert not (w.outbox / "bad.csv").exists()
    assert calls["n"] == 1


def test_debounce_enqueues_once(monkeypatch, tmp_path: Path):
    calls = {"n": 0}

    def fake_convert(in_path: Path, out_path: Path, *, transform: bool = True):
        calls["n"] += 1
        out_path.write_text("ok\n")
        return 1

    monkeypatch.setattr(w, "fit_to_csv", fake_convert)

    f = w.inbox / "burst.fit"
    f.write_bytes(b"123")

    handler = w.InboxHandler()
    t = _start_worker()

    class E:
        is_directory = False
        src_path = str(f)

    handler.on_modified(E())
    time.sleep(0.01)
    handler.on_modified(E())

    w._tasks.join()
    _stop_worker(t)

    assert (w.outbox / "burst.csv").exists()
    assert calls["n"] == 1
