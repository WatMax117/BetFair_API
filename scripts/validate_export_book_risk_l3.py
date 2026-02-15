#!/usr/bin/env python3
"""
Post-run validation for Book Risk L3 export output.
Usage: python scripts/validate_export_book_risk_l3.py <base_name>
  e.g. python scripts/validate_export_book_risk_l3.py book_risk_l3__vps2026-02-15

Expects files in data_exports/book_risk_l3/:
  {base_name}__part1.parquet
  {base_name}__part1.csv
  {base_name}__metadata.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data_exports" / "book_risk_l3"

REQUIRED_LONG_COLS = [
    "market_id", "snapshot_at_utc", "event_id", "event_start_time_utc",
    "home_team_name", "away_team_name", "market_type", "selection_id",
    "selection_name", "side", "total_volume",
    "back_odds_l1", "back_size_l1", "back_odds_l2", "back_size_l2",
    "back_odds_l3", "back_size_l3",
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_export_book_risk_l3.py <base_name>")
        print("  e.g. validate_export_book_risk_l3.py book_risk_l3__vps2026-02-15123456")
        sys.exit(1)

    base_name = sys.argv[1].replace(".parquet", "").replace(".csv", "").replace("__metadata.json", "").rstrip("_")
    parquet_path = OUTPUT_DIR / f"{base_name}__part1.parquet"
    csv_path = OUTPUT_DIR / f"{base_name}__part1.csv"
    meta_path = OUTPUT_DIR / f"{base_name}__metadata.json"

    errors = []

    # 1. Files exist
    for p, label in [(parquet_path, "Parquet"), (csv_path, "CSV"), (meta_path, "Metadata JSON")]:
        if not p.exists():
            errors.append(f"Missing {label}: {p}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    # 2. Load metadata
    with open(meta_path) as f:
        meta = json.load(f)
    snapshot_count = meta.get("snapshot_count", 0)
    record_count = meta.get("record_count", 0)

    # 3. Load long Parquet
    df_long = pd.read_parquet(parquet_path)

    # 4. Required columns
    missing_cols = [c for c in REQUIRED_LONG_COLS if c not in df_long.columns]
    if missing_cols:
        errors.append(f"Long format missing columns: {missing_cols}")

    # 5. Exactly 3 sides per (market_id, snapshot_at_utc)
    per_snapshot = df_long.groupby(["market_id", "snapshot_at_utc"]).size()
    bad = per_snapshot[per_snapshot != 3]
    if len(bad) > 0:
        errors.append(f"Found {len(bad)} (market_id, snapshot_at_utc) with != 3 sides: {bad.head().to_dict()}")

    # 6. No duplicates (market_id, snapshot_at_utc, side)
    dupes = df_long.duplicated(subset=["market_id", "snapshot_at_utc", "side"]).sum()
    if dupes > 0:
        errors.append(f"Found {dupes} duplicate (market_id, snapshot_at_utc, side) rows")

    # 7. L1 <= L2 <= L3 (odds ascending = best price first) - warn only (source may have edge cases)
    ladder_violations = 0
    for _, row in df_long.iterrows():
        l1, l2, l3 = row.get("back_odds_l1"), row.get("back_odds_l2"), row.get("back_odds_l3")
        if l1 is not None and l2 is not None and l1 > l2:
            ladder_violations += 1
            if ladder_violations <= 3:
                print(f"WARN: L1 > L2: market={row['market_id']} side={row['side']} l1={l1} l2={l2}")
        if l2 is not None and l3 is not None and l2 > l3:
            ladder_violations += 1
            if ladder_violations <= 3:
                print(f"WARN: L2 > L3: market={row['market_id']} side={row['side']} l2={l2} l3={l3}")
    if ladder_violations:
        print(f"WARN: {ladder_violations} ladder ordering violations (source data)")

    # 8. Row counts
    long_rows = len(df_long)
    expected_long = snapshot_count * 3
    if long_rows != expected_long and snapshot_count > 0:
        errors.append(f"Long row count mismatch: {long_rows} vs expected {expected_long} (snapshots*3)")

    # 9. Metadata counts
    df_wide = pd.read_csv(csv_path)
    wide_rows = len(df_wide)
    if wide_rows != snapshot_count and snapshot_count > 0:
        errors.append(f"Wide row count mismatch: {wide_rows} vs metadata snapshot_count {snapshot_count}")

    # 10. UTC ISO-8601
    for col in ["snapshot_at_utc", "event_start_time_utc"]:
        if col not in df_long.columns:
            continue
        sample = df_long[col].dropna().head(3)
        for v in sample:
            s = str(v)
            if "Z" not in s and "+" not in s and "T" in s:
                # Could be UTC without Z - acceptable
                pass
            elif "T" not in s:
                errors.append(f"{col} may not be ISO-8601: {s[:50]}")
                break

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    print("PASS: All validation checks")
    print(f"  Long rows: {long_rows} (expected {snapshot_count} x 3)")
    print(f"  Wide rows: {wide_rows}")
    print(f"  Markets: {meta.get('market_count', 'N/A')}")
    print(f"  Min snapshot: {meta.get('min_snapshot_at', 'N/A')}")
    print(f"  Max snapshot: {meta.get('max_snapshot_at', 'N/A')}")


if __name__ == "__main__":
    main()
