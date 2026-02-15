#!/usr/bin/env python3
"""
Event-level coverage summary from Book Risk L3 long Parquet export.

Computes per-market temporal coverage relative to kickoff and a coverage_flag (PASS/FAIL).
Run locally (no Docker): python scripts/event_coverage_analysis.py [parquet_path]

Output: <run_prefix>__event_coverage_summary.parquet and .csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Default input (local path)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARQUET = PROJECT_ROOT / "data_exports/book_risk_l3/book_risk_l3__vps2026-02-15082222__part1.parquet"
OUTPUT_DIR = PROJECT_ROOT / "data_exports/book_risk_l3"


def parse_utc(s: pd.Series) -> pd.Series:
    """Parse ISO-8601 UTC strings to datetime (timezone-aware UTC)."""
    return pd.to_datetime(s, utc=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Event coverage summary from Book Risk L3 Parquet")
    ap.add_argument("parquet", nargs="?", default=str(DEFAULT_PARQUET), help="Long-format Parquet path")
    args = ap.parse_args()

    path = Path(args.parquet)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(path)
    # One row per (market_id, snapshot_at_utc, side) — take one per snapshot for time logic
    snapshot_at = parse_utc(df["snapshot_at_utc"])
    event_start = parse_utc(df["event_start_time_utc"])

    df = df.assign(
        snapshot_at_dt=snapshot_at,
        event_start_dt=event_start,
        t_to_kickoff_min=(event_start - snapshot_at).dt.total_seconds() / 60,
        t_from_kickoff_min=(snapshot_at - event_start).dt.total_seconds() / 60,
    )
    df["pre_match"] = df["snapshot_at_dt"] < df["event_start_dt"]
    df["in_match_window"] = (df["t_from_kickoff_min"] >= 0) & (df["t_from_kickoff_min"] <= 105)
    df["end_window"] = (df["t_from_kickoff_min"] >= 105) & (df["t_from_kickoff_min"] <= 135)

    # One row per (market_id, snapshot_at_utc) for aggregation
    snap = df.drop_duplicates(subset=["market_id", "snapshot_at_utc"]).copy()

    agg = snap.groupby("market_id").agg(
        event_id=("event_id", "first"),
        event_start_time_utc=("event_start_time_utc", "first"),
        home_team_name=("home_team_name", "first"),
        away_team_name=("away_team_name", "first"),
        snapshots_total=("snapshot_at_utc", "nunique"),
        snapshots_pre_match=("pre_match", "sum"),
        snapshots_in_match=("in_match_window", "sum"),
        snapshots_end_window=("end_window", "sum"),
        first_snapshot_at=("snapshot_at_dt", "min"),
        last_snapshot_at=("snapshot_at_dt", "max"),
    ).reset_index()

    def last_pre_match_at(g: pd.DataFrame) -> pd.Timestamp | None:
        pre = g[g["pre_match"]]
        return pre["snapshot_at_dt"].max() if len(pre) else None

    last_pre = snap.groupby("market_id").apply(last_pre_match_at, include_groups=False)
    agg["last_pre_match_snapshot_at"] = agg["market_id"].map(last_pre)

    kickoff = parse_utc(agg["event_start_time_utc"])
    agg["last_pre_match_gap_min"] = (kickoff - pd.to_datetime(agg["last_pre_match_snapshot_at"], utc=True)).dt.total_seconds() / 60
    agg["final_snapshot_at"] = agg["last_snapshot_at"]
    # t_from_kickoff at final snapshot
    final_ts = agg.set_index("market_id")["final_snapshot_at"]
    snap["_final"] = snap["market_id"].map(final_ts)
    snap_final = snap[snap["snapshot_at_dt"] == snap["_final"]].drop_duplicates("market_id")
    agg["final_snapshot_t_from_kickoff_min"] = agg["market_id"].map(snap_final.set_index("market_id")["t_from_kickoff_min"])

    agg["has_pre_match"] = agg["snapshots_pre_match"] > 0
    agg["has_end_window"] = agg["snapshots_end_window"] > 0
    # has_closed_status: any snapshot after kickoff with market_status == 'CLOSED'
    after_kickoff = snap[snap["snapshot_at_dt"] >= snap["event_start_dt"]]
    closed_after = after_kickoff[after_kickoff["market_status"].astype(str).str.upper() == "CLOSED"].groupby("market_id").size()
    agg["has_closed_status"] = agg["market_id"].isin(closed_after.index)

    # Coverage flag
    def coverage_flag(row: pd.Series) -> str:
        if not row["has_pre_match"]:
            return "FAIL"
        if pd.isna(row["last_pre_match_gap_min"]) or row["last_pre_match_gap_min"] > 5:
            return "FAIL"
        if not row["has_end_window"] and not row["has_closed_status"]:
            return "FAIL"
        if pd.isna(row["final_snapshot_t_from_kickoff_min"]) or row["final_snapshot_t_from_kickoff_min"] < 100:
            return "FAIL"
        return "PASS"

    agg["coverage_flag"] = agg.apply(coverage_flag, axis=1)

    # Drop temp columns for output; keep string timestamps
    out_cols = [
        "market_id", "event_id", "event_start_time_utc", "home_team_name", "away_team_name",
        "snapshots_total", "snapshots_pre_match", "snapshots_in_match", "snapshots_end_window",
        "first_snapshot_at", "last_snapshot_at", "last_pre_match_snapshot_at", "last_pre_match_gap_min",
        "final_snapshot_at", "final_snapshot_t_from_kickoff_min",
        "has_pre_match", "has_end_window", "has_closed_status", "coverage_flag",
    ]
    out = agg[out_cols].copy()
    out["event_start_time_utc"] = out["event_start_time_utc"].astype(str)

    # Run prefix from parquet filename, e.g. book_risk_l3__vps2026-02-15082222__part1.parquet -> book_risk_l3__vps2026-02-15082222
    run_prefix = path.stem.replace("__part1", "").replace(".parquet", "")
    if not run_prefix.startswith("book_risk_l3"):
        run_prefix = "book_risk_l3__" + run_prefix

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_parquet = OUTPUT_DIR / f"{run_prefix}__event_coverage_summary.parquet"
    out_csv = OUTPUT_DIR / f"{run_prefix}__event_coverage_summary.csv"

    out.to_parquet(out_parquet, index=False)
    out.to_csv(out_csv, index=False)
    print(f"Wrote {out_parquet}")
    print(f"Wrote {out_csv}")

    n = len(out)
    n_pass = (out["coverage_flag"] == "PASS").sum()
    n_fail = (out["coverage_flag"] == "FAIL").sum()
    print(f"\nTotal events: {n}")
    print(f"PASS: {n_pass}")
    print(f"FAIL: {n_fail}")

    # Example FAIL reasons
    fail = out[out["coverage_flag"] == "FAIL"]
    if len(fail) > 0:
        print("\nExample FAIL cases (first 10):")
        for _, row in fail.head(10).iterrows():
            reasons = []
            if not row["has_pre_match"]:
                reasons.append("no pre-match snapshots")
            elif not pd.isna(row["last_pre_match_gap_min"]) and row["last_pre_match_gap_min"] > 5:
                reasons.append(f"last_pre_match_gap_min={row['last_pre_match_gap_min']:.1f}>5")
            if not row["has_end_window"] and not row["has_closed_status"]:
                reasons.append("missing end window and no CLOSED status")
            if pd.isna(row["final_snapshot_t_from_kickoff_min"]) or row["final_snapshot_t_from_kickoff_min"] < 100:
                reasons.append(f"final_snapshot_t_from_kickoff_min={row.get('final_snapshot_t_from_kickoff_min')} < 100")
            print(f"  {row['market_id']} {row['home_team_name']} v {row['away_team_name']}: {', '.join(reasons)}")


if __name__ == "__main__":
    main()
