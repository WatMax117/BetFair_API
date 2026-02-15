#!/usr/bin/env python3
"""Verify review export Parquet - run inside container on VPS."""
import os
import sys

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas required")
    sys.exit(1)

RUN_PREFIX = os.environ.get("RUN_PREFIX", "book_risk_l3__vps2026-02-15082222")
BASE = os.environ.get("WORK_DIR", "/work")
p = os.path.join(BASE, "data_exports/book_risk_l3/", RUN_PREFIX + "__part1.parquet")

if not os.path.exists(p):
    print(f"ERROR: file not found: {p}")
    sys.exit(1)

df = pd.read_parquet(p)
print("PARQUET:", p)
print("FILE_SIZE_BYTES:", os.path.getsize(p))
print("ROWS:", len(df))
print("COLS:", len(df.columns))
print("COLUMNS:", ",".join(df.columns))
print("SIDES_COUNT:", df["side"].value_counts(dropna=False).to_dict())
print("UNIQUE_SNAPSHOTS:", df[["market_id", "snapshot_at_utc"]].drop_duplicates().shape[0])
print("UNIQUE_MARKETS:", df["market_id"].nunique())
print("HEAD:", df.head(3).to_dict(orient="records"))
