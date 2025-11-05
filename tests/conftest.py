import importlib
import logging
import os
from pathlib import Path

import pytest

from fit_converter.converter import ConversionReport


@pytest.fixture(autouse=True)
def _isolate_env_and_paths_cache(monkeypatch):
    # 1) Nuke env that can affect path resolution/config
    for k in list(os.environ):
        if k.startswith("APP_") or k.startswith("FIT_CONVERTER_"):
            monkeypatch.delenv(k, raising=False)

    # 2) Clear the lru_cache used by resolve_runtime_paths()
    #    so each test sees the env it sets.
    import fit_converter.paths as p

    p.resolve_runtime_paths.cache_clear()


@pytest.fixture(autouse=True)
def _reset_logging_between_tests():
    # Remove all handlers from root
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    # Optionally silence root to a safe level
    root.setLevel(logging.WARNING)

    # Clear the idempotency guard on configure_logging
    try:
        import fit_converter.logging_setup as ls

        if hasattr(ls.configure_logging, "_configured"):
            delattr(ls.configure_logging, "_configured")
        importlib.reload(ls)  # keep things fresh if tests import the module directly
    except Exception:
        pass


@pytest.fixture
def fake_convert_factory(tmp_path):
    """
    Returns a factory that produces a fake convert_with_report implementation
    along with a `calls` dict you can examine in your test.
    Usage:
        fake, calls = fake_convert_factory(ok=True, rows=5)
        monkeypatch.setattr(module, "convert_with_report", fake)
    Then after running logic you can inspect calls["n"] etc.
    """

    def _make(*, ok=True, rows=None, seconds=0.0, message="fake success"):
        calls = {"n": 0}

        def _fake(
            in_path: Path,
            out_path: Path,
            *,
            transform=True,
            logger=None,
            quiet_logs=False,
        ):
            calls["n"] += 1
            if not ok:
                return ConversionReport(
                    ok=False, rows=None, seconds=None, message=message
                )
            # simulate writing output so outbox path exists
            out_path.write_text("csv\n")
            return ConversionReport(
                ok=True,
                rows=rows if rows is not None else 0,
                seconds=seconds,
                message=message,
            )

        return _fake, calls

    return _make
