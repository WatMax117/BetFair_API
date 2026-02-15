#!/usr/bin/env python3
"""
Event Coverage Diagnostics – determine why 0 PASS.

Steps 1–3, 5–8: full-lifecycle check, CLOSED count, snapshot distribution,
pre-match integrity, soft_pass, end-window 90–150 min.
Run on long Parquet: python scripts/event_coverage_diagnostics.py [path/to/part1.parquet]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARQUET = PROJECT_ROOT / "data_exports/book_risk_l3/book_risk_l3__vps2026-02-15082222__part1.parquet"


def main() -> None:
    ap = argparse.ArgumentParser(description="Event coverage diagnostics")
    ap.add_argument("parquet", nargs="?", default=str(DEFAULT_PARQUET), help="Long Parquet path")
    args = ap.parse_args()
    path = Path(args.parquet)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(path)
    snapshot_at = pd.to_datetime(df["snapshot_at_utc"], utc=True)
    event_start = pd.to_datetime(df["event_start_time_utc"], utc=True)
    df = df.assign(
        snapshot_at_dt=snapshot_at,
        event_start_dt=event_start,
        t_from_kickoff_min=(snapshot_at - event_start).dt.total_seconds() / 60,
    )
    # One row per (market_id, snapshot_at_utc)
    snap = df.drop_duplicates(subset=["market_id", "snapshot_at_utc"]).copy()

    print("=" * 60)
    print("Step 4 – Export filters (from export_book_risk_l3.py)")
    print("=" * 60)
    print("  Time filter: snapshot_at >= date_from AND snapshot_at < date_to (explicit window only)")
    print("  Status filter: NONE (OPEN/CLOSED/SUSPENDED all included)")
    print("  LIMIT: NONE")
    print("  Partition: part1, part2, ... by max_rows_per_file (no truncation of time)")
    print("  Conclusion: Export is strictly bounded by date_from/date_to; no extra cutoff.")

    print("\n" + "=" * 60)
    print("Step 1 – Full-lifecycle: max(snapshot - event_start) per market (minutes)")
    print("=" * 60)
    max_min = snap.groupby("market_id")["t_from_kickoff_min"].max()
    print(f"Events with final_snapshot_t_from_kickoff_min >= 100: {(max_min >= 100).sum()}")
    print(f"Events with final in [60, 100): {(max_min >= 60).sum() - (max_min >= 100).sum()}")
    print(f"Events with final in [0, 60):   {((max_min >= 0) & (max_min < 60)).sum()}")
    print(f"Events with final < 0 (pre-match only): {(max_min < 0).sum()}")
    print("\nMax t_from_kickoff_min per market (sample, sorted desc):")
    for mid, val in max_min.nlargest(10).items():
        print(f"  {mid}: {val:.1f} min")
    print("\nRed flag: most events cap at 45–60 min or negative?")
    cap_45_60 = ((max_min >= 40) & (max_min <= 65)).sum()
    print(f"  Events with max in [40, 65] min: {cap_45_60}")

    print("\n" + "=" * 60)
    print("Step 2 – CLOSED market status")
    print("=" * 60)
    status_upper = df["market_status"].astype(str).str.strip().str.upper()
    closed = df[status_upper == "CLOSED"]
    closed_per_market = closed.groupby("market_id").size()
    print(f"Rows with market_status == 'CLOSED': {len(closed)}")
    print(f"Markets with at least one CLOSED: {len(closed_per_market)}")
    if len(closed_per_market) > 0:
        print("  Sample market_ids:", closed_per_market.head(5).index.tolist())
    else:
        print("  Red flag: CLOSED never appears.")

    print("\n" + "=" * 60)
    print("Step 3 – Snapshot distribution (sample failing events)")
    print("=" * 60)
    # Pick a few markets: one that stops ~60 min, one pre-match only (if any)
    max_min_df = max_min.reset_index(name="max_t")
    stop_60 = max_min_df[(max_min_df["max_t"] >= 50) & (max_min_df["max_t"] <= 65)].head(1)
    pre_only = max_min_df[max_min_df["max_t"] < 0].head(1)
    samples = []
    if len(stop_60) > 0:
        samples.append(("Stops ~60 min", stop_60["market_id"].iloc[0]))
    if len(pre_only) > 0:
        samples.append(("Pre-match only", pre_only["market_id"].iloc[0]))
    if not samples:
        samples = [(f"Max t={max_min_df['max_t'].iloc[0]:.0f} min", max_min_df["market_id"].iloc[0])]
    for label, mid in samples:
        sub = snap[snap["market_id"] == mid].sort_values("snapshot_at_dt")
        print(f"\n{label} (market_id={mid}):")
        print(sub[["snapshot_at_dt", "t_from_kickoff_min"]].head(5).to_string(index=False))
        print("  ...")
        print(sub[["snapshot_at_dt", "t_from_kickoff_min"]].tail(5).to_string(index=False))
        print(f"  Count: {len(sub)}, t_from_kickoff range: [{sub['t_from_kickoff_min'].min():.1f}, {sub['t_from_kickoff_min'].max():.1f}] min")

    print("\n" + "=" * 60)
    print("Step 5 – Pre-match window integrity")
    print("=" * 60)
    pre = snap[snap["snapshot_at_dt"] < snap["event_start_dt"]]
    last_pre = pre.groupby("market_id")["snapshot_at_dt"].max()
    kickoff = snap.groupby("market_id")["event_start_dt"].first()
    gap_min = (kickoff - last_pre).dt.total_seconds() / 60
    has_pre = last_pre.notna()
    print(f"Events with at least one pre-match snapshot: {has_pre.sum()}")
    print(f"Of those, last pre-match gap <= 5 min: {(gap_min <= 5).sum()}")
    print(f"Of those, last pre-match gap in (5, 20] min: {((gap_min > 5) & (gap_min <= 20)).sum()}")
    if has_pre.sum() > 0:
        print("  Sample last_pre_match_gap_min (where > 5):")
        sample = gap_min[(gap_min > 5) & (gap_min < 1000)].head(5)
        for mid, g in sample.items():
            print(f"    {mid}: {g:.1f} min")

    print("\n" + "=" * 60)
    print("Step 7 – Soft pass (has_pre_match AND final_snapshot_t_from_kickoff_min >= 60)")
    print("=" * 60)
    soft_pass = has_pre & (max_min >= 60)
    print(f"soft_pass count: {soft_pass.sum()}")
    if soft_pass.sum() > 0:
        print("  Sample market_ids:", max_min[soft_pass].head(5).index.tolist())

    print("\n" + "=" * 60)
    print("Step 8 – End window 90–150 min (wider than 105–135)")
    print("=" * 60)
    in_90_150 = snap[(snap["t_from_kickoff_min"] >= 90) & (snap["t_from_kickoff_min"] <= 150)]
    markets_90_150 = in_90_150["market_id"].nunique()
    print(f"Snapshots in 90–150 min from kickoff: {len(in_90_150)}")
    print(f"Markets with at least one snapshot in 90–150 min: {markets_90_150}")
    if markets_90_150 == 0:
        print("  Red flag: no late snapshots exist in dataset.")

    print("\n" + "=" * 60)
    print("Step 6 – Diagnostic matrix summary")
    print("=" * 60)
    no_after_60 = (max_min < 60).sum()
    no_closed = len(closed_per_market) == 0
    print("| Symptom | Likely cause |")
    print("|---------|--------------|")
    print(f"| No snapshots after ~60 min for {no_after_60} events | Collector failure or export window |")
    print(f"| No CLOSED ever recorded ({no_closed}) | Status filter or collector ends early |")
    print("| Many pre-kickoff-only / negative max_t | Future matches or incomplete window |")

    print("\nDone.")


if __name__ == "__main__":
    main()
