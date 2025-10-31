# tests/test_watcher.py
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

import fit_converter.watcher as w

# from fit_converter.converter import ConversionError, ConversionReport


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


def test_retry_then_success(monkeypatch, tmp_path: Path, fake_convert_factory):

    attempt = {"first": True}

    # Create fake convert function that fails first then succeeds
    fake, calls = fake_convert_factory(
        ok=True, rows=1, seconds=0.0, message="dummy success"
    )

    # Wrap the fake so that the first call still fails
    def fake_with_failure(
        in_path, out_path, *, transform=True, logger=None, quiet_logs=False
    ):
        if attempt["first"]:
            calls["n"] += 1
            attempt["first"] = False
            raise RuntimeError("temporary failure")
        # After first attempt, call the normal fake behavior
        return fake(
            in_path, out_path, transform=transform, logger=logger, quiet_logs=quiet_logs
        )

    monkeypatch.setattr(w, "convert_with_report", fake_with_failure)

    f = w.inbox / "run.fit"
    f.write_bytes(b"fakefit")

    t = _start_worker()
    w._tasks.put(f)
    w._tasks.join()
    _stop_worker(t)

    assert (w.outbox / "run.csv").exists()
    assert calls["n"] == 2


def test_conversion_error_no_retry(monkeypatch, tmp_path: Path, fake_convert_factory):
    fake, calls = fake_convert_factory(ok=False, message="corrupt FIT")
    monkeypatch.setattr(w, "convert_with_report", fake)

    f = w.inbox / "bad.fit"
    f.write_bytes(b"xxxx")

    t = _start_worker()
    w._tasks.put(f)
    w._tasks.join()
    _stop_worker(t)

    assert not (w.outbox / "bad.csv").exists()
    assert calls["n"] == 1


def test_debounce_enqueues_once(monkeypatch, tmp_path: Path, fake_convert_factory):
    fake, calls = fake_convert_factory(
        ok=True, rows=2104, seconds=2.06, message="success"
    )

    monkeypatch.setattr(w, "convert_with_report", fake)

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


def test_generic_failure_all_retries(monkeypatch, tmp_path: Path, fake_convert_factory):
    fake, calls = fake_convert_factory(ok=False, message="generic error")

    # Wrap without returning a ConversionReport — just raise generic Exception
    def fake_always_fail(
        in_path, out_path, *, transform=True, logger=None, quiet_logs=False
    ):
        calls["n"] += 1
        raise RuntimeError("system failure")

    monkeypatch.setattr(w, "convert_with_report", fake_always_fail)

    f = w.inbox / "failme.fit"
    f.write_bytes(b"fake data")

    t = _start_worker()
    w._tasks.put(f)
    w._tasks.join()
    _stop_worker(t)

    assert not (w.outbox / "failme.csv").exists()
    assert calls["n"] == w.RETRIES  # i.e., 3
