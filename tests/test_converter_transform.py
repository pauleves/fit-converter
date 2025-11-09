from __future__ import annotations

import csv
from pathlib import Path

import pytest

from fit_converter.converter import _pace_mmss_from_mps, fit_to_csv


class _FakeMessage:
    def __init__(self, values: dict[str, object]):
        self._values = values

    def get_values(self) -> dict[str, object]:
        return dict(self._values)


def _patch_fitfile(monkeypatch: pytest.MonkeyPatch, records: list[dict[str, object]]):
    class _FakeFitFile:
        def __init__(self, _path: str):
            self._messages = [_FakeMessage(r) for r in records]

        def get_messages(self, name: str):
            assert name == "record"
            return list(self._messages)

    monkeypatch.setattr("fit_converter.converter.FitFile", _FakeFitFile)


def _run_conversion(
    tmp_path: Path, records: list[dict[str, object]], *, transform: bool
):
    in_path = tmp_path / "sample.fit"
    in_path.write_bytes(b"fake-fit")
    out_path = tmp_path / "out.csv"
    rows = fit_to_csv(in_path, out_path, transform=transform)
    with out_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        data = list(reader)
    return rows, fieldnames, data


def test_transform_prefers_enhanced_speed_once(monkeypatch, tmp_path):
    records = [
        {"timestamp": 1, "speed": 2.0, "enhanced_speed": 2.2, "cadence": 80},
        {"timestamp": 2, "speed": 2.1, "enhanced_speed": 2.3, "cadence": 82},
    ]
    _patch_fitfile(monkeypatch, records)

    rows, header, data = _run_conversion(tmp_path, records, transform=True)

    assert rows == len(records)
    assert header.count("pace_mm_ss_per_mile") == 1
    assert "speed" not in header
    assert "enhanced_speed" not in header
    assert header == ["timestamp", "pace_mm_ss_per_mile", "cadence_spm"]

    expected_first_pace = _pace_mmss_from_mps(records[0]["enhanced_speed"])
    assert data[0]["pace_mm_ss_per_mile"] == expected_first_pace
    # cadence doubles per-leg cadence to steps per minute
    assert float(data[0]["cadence_spm"]) == pytest.approx(160.0)


def test_transform_falls_back_to_speed(monkeypatch, tmp_path):
    records = [
        {"timestamp": 10, "speed": 3.0},
        {"timestamp": 11, "speed": 2.5},
    ]
    _patch_fitfile(monkeypatch, records)

    rows, header, data = _run_conversion(tmp_path, records, transform=True)

    assert rows == len(records)
    assert header == ["timestamp", "pace_mm_ss_per_mile"]

    expected = [_pace_mmss_from_mps(r["speed"]) for r in records]
    actual = [row["pace_mm_ss_per_mile"] for row in data]
    assert actual == expected
