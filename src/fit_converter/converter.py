from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from fitparse import FitFile

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Raised when a FIT→CSV conversion fails in a recoverable way."""


_HUMAN_ERROR_MAP = {
    "truncated": "file appears truncated",
    "crc": "file failed CRC check (corrupted data)",
    "unsupported_profile": "FIT profile not supported",
    "decode": "could not decode FIT stream",
}


def _humanise_conversion_error(exc: Exception) -> str:
    t = str(exc).lower()
    for k, msg in _HUMAN_ERROR_MAP.items():
        if k in t:
            return msg
    return "could not convert file"


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


@dataclass
class ConversionReport:
    ok: bool
    rows: int | None
    seconds: float | None
    message: str  # success summary or human error text


def convert_with_report(
    in_path: Path,
    out_path: Path,
    *,
    transform: bool,
    logger: logging.Logger = None,
    count_rows_if_missing: bool = True,
    quiet_logs: bool = False,
) -> ConversionReport:
    """
    Wrap fit_to_csv with timing + friendly logging.
    Returns a report so callers can also surface status in UI if needed.
    """
    try:
        t0 = time.perf_counter()
        rows = fit_to_csv(in_path, out_path, transform=transform)
        dt = time.perf_counter() - t0

        # If fit_to_csv doesn't return a count, optionally derive it
        if rows is None and count_rows_if_missing:
            try:
                # subtract header
                with open(out_path, "r", encoding="utf-8", newline="") as f:
                    rows = max(0, sum(1 for _ in f) - 1)
            except Exception:
                rows = None

        msg = f"✅ converted: {in_path.name} → {out_path.name} ({rows if rows is not None else '?'} rows, {dt:.2f} s)"
        if not quiet_logs:
            logger.info(msg)
        return ConversionReport(ok=True, rows=rows, seconds=dt, message=msg)

    except ConversionError as e:
        msg = f"❌ {in_path.name} — {_humanise_conversion_error(e)}"
        if not quiet_logs:
            logger.error(msg)
        return ConversionReport(ok=False, rows=None, seconds=None, message=msg)


def fit_to_csv(
    in_path: Path | str,
    out_path: Path | str,
    fields: Iterable[str] | None = None,
    transform: bool = False,
) -> int:
    """Convert a .fit file to CSV."""
    try:
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

        raw_header = list(header)

        if transform:
            # Transform column names while keeping order; only ever emit a single pace column.
            new_header: list[str] = []
            pace_added = False
            for name in raw_header:
                if name == "cadence":
                    new_header.append("cadence_spm")
                elif name in ("speed", "enhanced_speed"):
                    if not pace_added:
                        new_header.append("pace_mm_ss_per_mile")
                        pace_added = True
                elif name == "position_lat":
                    new_header.append("latitude_deg")
                elif name == "position_long":
                    new_header.append("longitude_deg")
                else:
                    new_header.append(name)
            header = new_header

        header_set = set(header)

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
                    if "cadence_spm" in header_set:
                        raw_cadence = values.get("cadence")
                        row["cadence_spm"] = _to_spm(raw_cadence)

                    # --- speed/enhanced_speed → pace_min_per_mile (single column) ---
                    if "pace_mm_ss_per_mile" in header_set:
                        raw_speed = values.get("enhanced_speed")
                        if raw_speed is None:
                            raw_speed = values.get("speed")
                        row["pace_mm_ss_per_mile"] = _pace_mmss_from_mps(raw_speed)

                    # --- coords semicircles → degrees (replace) ---
                    if "latitude_deg" in header_set:
                        row["latitude_deg"] = _semicircles_to_degrees(
                            values.get("position_lat")
                        )
                    if "longitude_deg" in header_set:
                        row["longitude_deg"] = _semicircles_to_degrees(
                            values.get("position_long")
                        )
                writer.writerow(row)
                rows_written += 1

        return rows_written

    except (ValueError, KeyError) as e:
        # fitparse / decode / schema issues → user/data error
        raise ConversionError(f"Bad FIT data: {e}") from e
    except OSError as e:
        # file I/O issues
        raise ConversionError(f"I/O failure: {e}") from e


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 3:
        logger.info(
            "Usage: python fit_to_csv.py <input.fit> <output.csv> [--transform]"
        )
        raise SystemExit(2)

    in_file = Path(sys.argv[1])
    out_file = Path(sys.argv[2])
    transform_flag = "--transform" in sys.argv

    n = fit_to_csv(in_file, out_file, transform=transform_flag)
    logger.info(
        f"Wrote {n} rows to {out_file} {'(transformed)' if transform_flag else ''}"
    )
