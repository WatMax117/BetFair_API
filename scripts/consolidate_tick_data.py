#!/usr/bin/env python3
"""
Produce a consolidated CSV from exported tick-level data.

Reads per-market Parquet or JSONL from markets/ in the export directory, joins
metadata from index and optional metadata JSONs, deduplicates, sorts globally,
and writes consolidated_ticks.csv plus consolidation_report.txt.

Single-day trial: use --date YYYY-MM-DD to limit to one UTC calendar day.
Output: consolidated_ticks_YYYY_MM_DD.csv and consolidation_report_YYYY_MM_DD.txt.

Usage:
  python scripts/consolidate_tick_data.py --export-dir data_exports/tick_export
  python scripts/consolidate_tick_data.py --export-dir data_exports/tick_export --date 2024-01-15
  python scripts/consolidate_tick_data.py --export-dir data_exports/tick_export --chunk-rows 1000000

Requires: pandas, pyarrow (for Parquet).
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data_exports" / "tick_export"
CONSOLIDATED_CSV = "consolidated_ticks.csv"
CONSOLIDATION_REPORT = "consolidation_report.txt"
CHUNK_ROWS_DEFAULT = 1_500_000  # Write temp partition when buffer exceeds this
PARTITION_THRESHOLD_GB = 8  # If final CSV > this, also write year-month partitions

# Strict schema column order
CSV_COLUMNS = [
    "received_at",
    "publish_time",
    "market_id",
    "event_id",
    "selection_id",
    "side",
    "level",
    "price",
    "size",
    "traded_volume",
    "in_play",
    "change_type",
    "sequence",
    "record_type",
    "market_status",
    "market_start_time",
    "market_type",
    "runner_name",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("consolidate_tick_data")


def utc_iso(ts: Any) -> str:
    """Format timestamp as UTC ISO 8601 with Z. None -> empty string."""
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return ""
    if isinstance(ts, str):
        return ts
    if hasattr(ts, "tz_localize"):
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if hasattr(ts, "strftime"):
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc) if hasattr(ts, "replace") else ts
        return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return str(ts)


def load_index(export_dir: Path) -> tuple[list[dict], int]:
    """Load index.csv; return list of row dicts and expected total tick records (sum over non-zero)."""
    index_path = export_dir / "index.csv"
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found: {index_path}")
    rows = []
    expected_total = 0
    with open(index_path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
            try:
                n = int(row.get("total_tick_records", 0) or 0)
            except (TypeError, ValueError):
                n = 0
            expected_total += n
    return rows, expected_total


def load_metadata(export_dir: Path, market_id: str) -> Optional[dict]:
    """Load marketId=<id>_metadata.json if present."""
    path = export_dir / "markets" / f"marketId={market_id}_metadata.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load metadata %s: %s", path, e)
        return None


def runner_name_map(meta: Optional[dict]) -> dict[int, str]:
    """Build selection_id -> runner_name from metadata runners list."""
    if not meta or "runners" not in meta:
        return {}
    return {
        int(r["selectionId"]): (r.get("runnerName") or "")
        for r in meta.get("runners", [])
        if "selectionId" in r
    }


def read_parquet_file(path: Path) -> pd.DataFrame:
    """Read one Parquet file into DataFrame; normalize column names and types."""
    if not pd:
        raise RuntimeError("pandas required. pip install pandas pyarrow")
    df = pd.read_parquet(path)
    # Normalize: ensure snake_case and required columns
    rename = {}
    for c in list(df.columns):
        if c == "marketId":
            rename[c] = "market_id"
        elif c == "selectionId":
            rename[c] = "selection_id"
        elif c == "tradedVolume":
            rename[c] = "traded_volume"
        elif c == "changeType":
            rename[c] = "change_type"
    if rename:
        df = df.rename(columns=rename)
    if "in_play" not in df.columns:
        df["in_play"] = pd.NA
    if "sequence" not in df.columns:
        df["sequence"] = df.get("level", pd.Series(dtype="Int64"))
    return df


def read_jsonl_file(path: Path) -> pd.DataFrame:
    """Read one JSONL file into DataFrame; normalize to schema."""
    if not pd:
        raise RuntimeError("pandas required")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({
                "received_at": obj.get("received_at") or obj.get("receivedAt"),
                "publish_time": obj.get("publish_time") or obj.get("publishTime"),
                "market_id": obj.get("market_id") or obj.get("marketId"),
                "selection_id": obj.get("selection_id") or obj.get("selectionId"),
                "side": obj.get("side"),
                "level": obj.get("level"),
                "price": obj.get("price"),
                "size": obj.get("size"),
                "traded_volume": obj.get("traded_volume") or obj.get("tradedVolume"),
                "in_play": None,
                "change_type": obj.get("changeType") or obj.get("change_type", "update"),
                "sequence": obj.get("sequence") if "sequence" in obj else obj.get("level"),
                "record_type": obj.get("record_type", "ladder"),
            })
    if not rows:
        return pd.DataFrame(columns=CSV_COLUMNS)
    return pd.DataFrame(rows)


def normalize_row_to_flat(
    row: dict | Any,
    event_id: str = "",
    market_status: Optional[str] = None,
    market_start_time: Optional[str] = None,
    market_type: Optional[str] = None,
    runner_name: str = "",
) -> dict[str, Any]:
    """One row to flat dict with required columns; timestamps as UTC ISO strings."""
    if hasattr(row, "get"):
        r = row
    else:
        r = row._asdict() if hasattr(row, "_asdict") else dict(row)
    pt = r.get("publish_time")
    ra = r.get("received_at")
    side = r.get("side")
    if side is None or (isinstance(side, float) and pd.isna(side)):
        side = ""
    elif isinstance(side, str):
        side = side.strip().upper() or ""
    return {
        "received_at": utc_iso(ra),
        "publish_time": utc_iso(pt),
        "market_id": r.get("market_id") or "",
        "event_id": event_id,
        "selection_id": r.get("selection_id"),
        "side": side if side in ("BACK", "LAY") else side,
        "level": r.get("level"),
        "price": r.get("price"),
        "size": r.get("size"),
        "traded_volume": r.get("traded_volume"),
        "in_play": r.get("in_play"),
        "change_type": r.get("change_type") or "update",
        "sequence": r.get("sequence"),
        "record_type": r.get("record_type") or "ladder",
        "market_status": market_status or "",
        "market_start_time": market_start_time or "",
        "market_type": market_type or "",
        "runner_name": runner_name or "",
    }


def dedupe_key(row: dict) -> tuple:
    """Uniqueness key: market_id, selection_id, side, level, publish_time, sequence."""
    sid = row.get("selection_id")
    if sid is not None and pd.isna(sid):
        sid = None
    side = row.get("side") or ""
    level = row.get("level")
    if level is None or (isinstance(level, float) and pd.isna(level)):
        level = -1
    else:
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = -1
    seq = row.get("sequence")
    if seq is None or (isinstance(seq, float) and pd.isna(seq)):
        seq = -1
    else:
        try:
            seq = int(seq)
        except (TypeError, ValueError):
            seq = -1
    return (
        row.get("market_id") or "",
        sid,
        side,
        level,
        row.get("publish_time") or "",
        seq,
    )


def sort_key(row: dict) -> tuple:
    """Global sort: publish_time, market_id, selection_id, side (BACK before LAY), level, sequence."""
    pt = row.get("publish_time") or ""
    mid = row.get("market_id") or ""
    sid = row.get("selection_id")
    if sid is None or (isinstance(sid, float) and pd.isna(sid)):
        sid = -1
    side = row.get("side") or ""
    side_order = 0 if side == "BACK" else (1 if side == "LAY" else 2)
    level = row.get("level")
    if level is None or (isinstance(level, float) and pd.isna(level)):
        level = -1
    else:
        try:
            level = int(level)
        except (TypeError, ValueError):
            level = -1
    seq = row.get("sequence")
    if seq is None or (isinstance(seq, float) and pd.isna(seq)):
        seq = -1
    else:
        try:
            seq = int(seq)
        except (TypeError, ValueError):
            seq = -1
    return (pt, mid, sid, side_order, level, seq)


def dataframe_to_flat_rows(
    df: pd.DataFrame,
    meta: Optional[dict],
) -> list[dict]:
    """Convert DataFrame to list of flat dicts with metadata joined."""
    event_id = (meta.get("eventId") or "") if meta else ""
    market_status = meta.get("marketStatus") if meta else None
    market_start_time = meta.get("marketStartTime") if meta else None
    market_type = meta.get("marketType") if meta else None
    runners = runner_name_map(meta)
    out = []
    for _, r in df.iterrows():
        sid = r.get("selection_id")
        try:
            sid_int = int(sid) if sid is not None and not (isinstance(sid, float) and pd.isna(sid)) else None
        except (TypeError, ValueError):
            sid_int = None
        runner_name = runners.get(sid_int, "") if sid_int is not None else ""
        flat = normalize_row_to_flat(
            r,
            event_id=event_id,
            market_status=market_status,
            market_start_time=market_start_time,
            market_type=market_type,
            runner_name=runner_name,
        )
        out.append(flat)
    return out


def parse_utc_date(date_str: str) -> tuple[datetime, datetime]:
    """Parse YYYY-MM-DD and return (start_utc, end_utc) for that calendar day in UTC.
    start_utc: 2024-01-15 00:00:00+00 (inclusive)
    end_utc:   2024-01-16 00:00:00+00 (exclusive)
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError("--date must be YYYY-MM-DD")
    start_utc = datetime.strptime(date_str + " 00:00:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc


def filter_dataframe_by_publish_date(
    df: pd.DataFrame,
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    """Keep only rows where start_utc <= publish_time < end_utc (UTC). Modifies publish_time to be comparable."""
    if df is None or len(df) == 0:
        return df
    if "publish_time" not in df.columns:
        return df
    pt = pd.to_datetime(df["publish_time"], utc=True, errors="coerce")
    mask = (pt >= start_utc) & (pt < end_utc)
    return df.loc[mask].copy()


def load_market_ticks(export_dir: Path, market_id: str, file_path: str) -> Optional[pd.DataFrame]:
    """Load one market's tick file (Parquet or JSONL). Returns None if file missing."""
    markets_dir = export_dir / "markets"
    full = export_dir / file_path
    if not full.exists():
        # Try markets_dir + filename only
        name = Path(file_path).name
        full = markets_dir / name
    if not full.exists():
        return None
    try:
        if full.suffix.lower() == ".parquet":
            return read_parquet_file(full)
        if full.suffix.lower() == ".jsonl":
            return read_jsonl_file(full)
    except Exception as e:
        logger.warning("Failed to read %s: %s", full, e)
        return None
    return None


def _csv_cell(v: Any) -> str:
    """Format one cell for CSV; null/NaN -> empty string, no zero substitution."""
    if v is None:
        return ""
    if isinstance(v, float) and (v != v):  # NaN
        return ""
    if pd is not None and hasattr(pd, "isna") and pd.isna(v):
        return ""
    return str(v)


def write_csv_chunk(path: Path, rows: list[dict], columns: list[str]) -> None:
    """Write rows to CSV with header; nulls as empty (no zero)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            out = {k: _csv_cell(r.get(k)) for k in columns}
            w.writerow(out)


def merge_sorted_csvs(
    paths: list[Path],
    out_path: Path,
    columns: list[str],
    sort_key_fn,
    dedupe_key_fn,
) -> tuple[int, int]:
    """Merge sorted CSV files into one sorted CSV; dedupe by dedupe_key_fn. Returns (rows_written, dupes_removed)."""
    import heapq
    readers = []
    for p in paths:
        f = open(p, "r", encoding="utf-8", newline="")
        r = csv.DictReader(f)
        readers.append((f, r, p))
    heap = []
    for i, (f, r, _) in enumerate(readers):
        row = next(r, None)
        if row is not None:
            heapq.heappush(heap, (sort_key_fn(row), row, i))
    seen = set()
    written = 0
    dupes = 0
    with open(out_path, "w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        while heap:
            _, row, i = heapq.heappop(heap)
            k = dedupe_key_fn(row)
            if k in seen:
                dupes += 1
            else:
                seen.add(k)
                writer.writerow({c: row.get(c, "") for c in columns})
                written += 1
            f, r = readers[i][0], readers[i][1]
            next_row = next(r, None)
            if next_row is not None:
                heapq.heappush(heap, (sort_key_fn(next_row), next_row, i))
    for f, _, _ in readers:
        f.close()
    return written, dupes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate per-market tick export into a single CSV."
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Export root (contains index.csv and markets/)",
    )
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=CHUNK_ROWS_DEFAULT,
        help="Max rows in memory before writing temp partition (default %s)" % CHUNK_ROWS_DEFAULT,
    )
    parser.add_argument(
        "--partition-by-month",
        action="store_true",
        help="Also write partitioned CSVs by year-month when final size > %s GB" % PARTITION_THRESHOLD_GB,
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Single UTC calendar day: output consolidated_ticks_YYYY_MM_DD.csv and report for that day only",
    )
    args = parser.parse_args()
    export_dir = args.export_dir.resolve()
    if not export_dir.exists():
        logger.error("Export directory does not exist: %s", export_dir)
        return 1

    # Single-day mode: UTC boundaries and output names
    date_filter: Optional[tuple[datetime, datetime]] = None
    out_csv_name = CONSOLIDATED_CSV
    report_name = CONSOLIDATION_REPORT
    if args.date:
        try:
            start_utc, end_utc = parse_utc_date(args.date)
            date_filter = (start_utc, end_utc)
            # consolidated_ticks_2024_01_15.csv
            out_csv_name = f"consolidated_ticks_{args.date.replace('-', '_')}.csv"
            report_name = f"consolidation_report_{args.date.replace('-', '_')}.txt"
            logger.info("Single-day mode: UTC date %s (inclusive %s to exclusive %s)", args.date, start_utc.isoformat(), end_utc.isoformat())
        except ValueError as e:
            logger.error("%s", e)
            return 1

    start_time = time.perf_counter()
    index_rows, expected_total = load_index(export_dir)
    markets_with_ticks = [r for r in index_rows if int(r.get("total_tick_records") or 0) > 0]
    logger.info("Index: %s markets with ticks; expected total tick records: %s", len(markets_with_ticks), expected_total)

    all_rows: list[dict] = []
    temp_partition_paths: list[Path] = []
    chunk_rows = max(100_000, args.chunk_rows)
    total_dupes_in_chunks = 0
    total_rows_read_after_filter = 0  # for single-day report
    markets_included = 0  # markets that contributed at least one row

    for i, idx in enumerate(markets_with_ticks):
        market_id = idx.get("market_id") or ""
        file_path = idx.get("file_path") or ""
        if not file_path:
            continue
        df = load_market_ticks(export_dir, market_id, file_path)
        if df is None or len(df) == 0:
            continue
        if date_filter is not None:
            start_utc, end_utc = date_filter
            df = filter_dataframe_by_publish_date(df, start_utc, end_utc)
            if len(df) == 0:
                continue
            markets_included += 1
            total_rows_read_after_filter += len(df)
        meta = load_metadata(export_dir, market_id)
        rows = dataframe_to_flat_rows(df, meta)
        all_rows.extend(rows)
        if len(all_rows) >= chunk_rows:
            # Sort and dedupe this chunk, write temp
            all_rows.sort(key=sort_key)
            seen = set()
            unique = []
            for r in all_rows:
                k = dedupe_key(r)
                if k not in seen:
                    seen.add(k)
                    unique.append(r)
            dupes = len(all_rows) - len(unique)
            total_dupes_in_chunks += dupes
            temp_path = export_dir / f".consolidate_part_{len(temp_partition_paths):04d}.csv"
            write_csv_chunk(temp_path, unique, CSV_COLUMNS)
            temp_partition_paths.append(temp_path)
            logger.info("Chunk %s: %s rows (%s dupes removed) -> %s", len(temp_partition_paths), len(all_rows), dupes, temp_path.name)
            all_rows = []

    # Remaining rows
    if all_rows:
        all_rows.sort(key=sort_key)
        seen = set()
        unique = []
        for r in all_rows:
            k = dedupe_key(r)
            if k not in seen:
                seen.add(k)
                unique.append(r)
        dupes = len(all_rows) - len(unique)
        total_dupes_in_chunks += dupes
        temp_path = export_dir / f".consolidate_part_{len(temp_partition_paths):04d}.csv"
        write_csv_chunk(temp_path, unique, CSV_COLUMNS)
        temp_partition_paths.append(temp_path)

    # Merge or single output
    out_csv = export_dir / out_csv_name
    total_dupes_removed = 0
    total_written = 0

    if not temp_partition_paths:
        logger.info("No tick data to consolidate.")
        total_written = 0
    elif len(temp_partition_paths) == 1:
        # Single partition: dedupe and write
        with open(temp_partition_paths[0], "r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            rows = list(r)
        seen = set()
        unique = []
        for row in rows:
            k = dedupe_key(row)
            if k not in seen:
                seen.add(k)
                unique.append(row)
            else:
                total_dupes_removed += 1
        write_csv_chunk(out_csv, unique, CSV_COLUMNS)
        total_written = len(unique)
        temp_partition_paths[0].unlink(missing_ok=True)
    else:
        # Merge sorted partitions (global sort order) and dedupe during merge
        total_written, total_dupes_removed = merge_sorted_csvs(
            temp_partition_paths,
            out_csv,
            CSV_COLUMNS,
            sort_key,
            dedupe_key,
        )
        for p in temp_partition_paths:
            p.unlink(missing_ok=True)

    duplicates_removed = total_dupes_in_chunks + total_dupes_removed

    # Validation
    if date_filter is None and expected_total > 0 and total_written != expected_total:
        logger.warning(
            "Completeness mismatch: index total_tick_records=%s, consolidated rows=%s (diff=%s)",
            expected_total,
            total_written,
            expected_total - total_written,
        )

    # Earliest / latest publish_time from written file (sample or re-read first/last)
    earliest_pt = ""
    latest_pt = ""
    distinct_markets_in_output = 0
    if total_written > 0 and out_csv.exists():
        seen_markets: set[str] = set()
        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            first = next(r, None)
            if first:
                earliest_pt = first.get("publish_time") or ""
                seen_markets.add(first.get("market_id") or "")
            for row in r:
                latest_pt = row.get("publish_time") or latest_pt
                seen_markets.add(row.get("market_id") or "")
        distinct_markets_in_output = len(seen_markets)

    duration_sec = time.perf_counter() - start_time
    file_size = out_csv.stat().st_size if out_csv.exists() else 0

    # Single-day validation: all rows must fall strictly within the requested UTC day
    date_validation_ok = True
    if date_filter is not None and total_written > 0 and out_csv.exists():
        start_utc, end_utc = date_filter
        start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_utc.strftime("%Y-%m-%dT%H:%M:%S")
        out_of_range = 0
        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                pt = row.get("publish_time") or ""
                if pt < start_str or pt >= end_str:
                    out_of_range += 1
        date_validation_ok = out_of_range == 0
        if out_of_range:
            logger.warning("Date validation: %s rows have publish_time outside [%s, %s)", out_of_range, start_str, end_str)
        else:
            logger.info("Date validation: all rows within [%s, %s)", start_str, end_str)
        logger.info("Distinct market_id in output: %s", distinct_markets_in_output)

    # Report
    report_path = export_dir / report_name
    report_lines = [
        "Tick consolidation – execution report",
        "=======================================",
        f"Total markets processed: {len(markets_with_ticks)}",
        f"Total rows written: {total_written}",
        f"Duplicate rows removed: {duplicates_removed}",
        f"Earliest publish_time: {earliest_pt}",
        f"Latest publish_time: {latest_pt}",
        f"Final CSV file size (bytes): {file_size}",
        f"Processing duration (seconds): {duration_sec:.2f}",
    ]
    if date_filter is not None:
        start_utc, end_utc = date_filter
        report_lines = [
            "Tick consolidation – execution report (single UTC day)",
            "=======================================================",
            f"Selected UTC date: {args.date}",
            f"Start (inclusive): {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"End (exclusive):   {end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"Markets included: {markets_included}",
            f"Total rows read (after date filter): {total_rows_read_after_filter}",
            f"Rows before dedupe: {total_rows_read_after_filter}",
            f"Duplicates removed: {duplicates_removed}",
            f"Final rows written: {total_written}",
            f"Earliest publish_time: {earliest_pt}",
            f"Latest publish_time: {latest_pt}",
            f"Final CSV file size (bytes): {file_size}",
            f"Processing duration (seconds): {duration_sec:.2f}",
            f"Distinct market_id in output: {distinct_markets_in_output}",
            f"Date validation (all rows in range): {'PASS' if date_validation_ok else 'FAIL'}",
        ]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    logger.info("Consolidated CSV: %s (%s rows, %s bytes)", out_csv, total_written, file_size)
    logger.info("Report: %s", report_path)
    for line in report_lines:
        logger.info("  %s", line)

    # Optional: partition by year-month if large
    if args.partition_by_month and total_written > 0 and file_size > PARTITION_THRESHOLD_GB * (1024**3):
        logger.info("Partitioning by year-month (file > %s GB)...", PARTITION_THRESHOLD_GB)
        by_ym: dict[str, list[dict]] = {}
        with open(out_csv, "r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                pt = row.get("publish_time") or ""
                if len(pt) >= 7:
                    ym = pt[:7].replace("-", "_")  # 2024-01 -> 2024_01
                else:
                    ym = "unknown"
                by_ym.setdefault(ym, []).append(row)
        for ym, part_rows in by_ym.items():
            part_path = export_dir / f"consolidated_ticks_{ym}.csv"
            write_csv_chunk(part_path, part_rows, CSV_COLUMNS)
            logger.info("Partition %s: %s rows -> %s", ym, len(part_rows), part_path.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
