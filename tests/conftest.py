from pathlib import Path

import pytest

from fit_converter.converter import ConversionReport


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
