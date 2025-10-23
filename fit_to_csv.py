from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence

from fitparse import FitFile


def _to_spm(cadence: float | int | None) -> float | None:
    # Garmin run cadence is often per-leg; double to steps/min
    if cadence is None:
        return None
    try:
        return float(cadence) * 2.0
    except (TypeError, ValueError):
        return None


def _semicircles_to_degrees(value):
    if value is None:
        return None
    try:
        return float(value) * (180.0 / (2**31))
    except (TypeError, ValueError):
        return None


def _pace_mmss_from_mps(speed_mps):
    """m/s → 'mm:ss' per mile; returns None if speed <= 0 or missing."""
    try:
        v = float(speed_mps)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    sec_per_mile = 1609.344 / v
    m = int(sec_per_mile // 60)
    s = int(round(sec_per_mile - m * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m:02d}:{s:02d}"


def fit_to_csv(
    in_path: Path | str,
    out_path: Path | str,
    fields: Iterable[str] | None = None,
    transform: bool = False,
) -> int:
    """Convert a .fit file to CSV."""
    in_path = Path(in_path)
    out_path = Path(out_path)

    if not in_path.exists() or not in_path.is_file():
        raise FileNotFoundError(f"Input file not found: {in_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # -------- Discover all keys across all records -------
    # By nature FIT files may have different length records

    all_keys: set[str] = set()
    fit = FitFile(str(in_path))
    for msg in fit.get_messages("record"):
        values = msg.get_values()
        all_keys.update(values.keys())

    if not all_keys:
        raise ValueError(f"No 'record' messages in FIT file: {in_path}")

    # If caller supplied fields, respect them; otherwise build a sensible header
    if fields is not None:
        header: Sequence[str] = list(fields)
    else:
        preferred = [
            "timestamp",
            "position_lat",
            "position_long",
            "distance",
            "speed",
            "heart_rate",
            "cadence",
            "temperature",
        ]
        # preferred first (only those that actually exist), then the rest sorted
        existing_preferred = [k for k in preferred if k in all_keys]
        header = existing_preferred + sorted(all_keys - set(existing_preferred))

    if transform:
        # cadence → cadence_spm (you already have this)
        if "cadence" in header:
            header = [("cadence_spm" if h == "cadence" else h) for h in header]

        # speed/enhanced_speed → pace_min_per_mile (prefer enhanced_speed as the source)
        # We only expose a single pace column to keep CSV tidy.
        if "speed" in header or "enhanced_speed" in header:
            header = [
                ("pace_mm_ss_per_mile" if h in ("speed", "enhanced_speed") else h)
                for h in header
            ]
            # If both existed, we just keep one pace column name

        # position_lat/position_long (semicircles) → degrees columns
        if "position_lat" in header:
            header = [("latitude_deg" if h == "position_lat" else h) for h in header]
        if "position_long" in header:
            header = [("longitude_deg" if h == "position_long" else h) for h in header]

    # -------- Write the CSV using the union header -------
    fit = FitFile(str(in_path))
    rows_written = 0

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        for msg in fit.get_messages("record"):
            values = msg.get_values()
            row = {name: values.get(name) for name in header}
            if transform:
                # --- cadence → cadence_spm (replace) ---
                raw_cadence = values.get("cadence")
                row["cadence_spm"] = _to_spm(raw_cadence)

                # --- speed/enhanced_speed → pace_min_per_mile (replace both with one) ---
                raw_speed = values.get("enhanced_speed")
                if raw_speed is None:
                    raw_speed = values.get("speed")
                row["pace_mm_ss_per_mile"] = _pace_mmss_from_mps(raw_speed)

                # --- coords semicircles → degrees (replace) ---
                row["latitude_deg"] = _semicircles_to_degrees(
                    values.get("position_lat")
                )
                row["longitude_deg"] = _semicircles_to_degrees(
                    values.get("position_long")
                )
            writer.writerow(row)
            rows_written += 1

    return rows_written


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        print("Usage: python fit_to_csv.py <input.fit> <output.csv> [--transform]")
        raise SystemExit(2)

    in_file = Path(sys.argv[1])
    out_file = Path(sys.argv[2])
    transform_flag = "--transform" in sys.argv

    n = fit_to_csv(in_file, out_file, transform=transform_flag)
    print(f"Wrote {n} rows to {out_file} {'(transformed)' if transform_flag else ''}")
