#!/usr/bin/env python3
"""
Snapshot Inventory Audit for Backfill Eligibility

Audits market_derived_metrics and market_book_snapshots to determine:
- What historical data exists
- Which parameters can be reconstructed from raw_payload
- Eligibility matrix for backfill

Run on VPS: python3 risk-analytics-ui/scripts/audit_snapshot_inventory.py
"""

import json
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

# DB connection (adjust for your environment)
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "netbet",
    "user": "netbet",
    "password": "netbet",
}


def get_conn():
    """Open DB connection."""
    return psycopg2.connect(**DB_CONFIG)


def audit_snapshot_counts(conn) -> Dict:
    """A) Snapshot inventory: total count, oldest, latest."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                COUNT(*) AS total_snapshots,
                MIN(snapshot_at) AS oldest_snapshot,
                MAX(snapshot_at) AS latest_snapshot
            FROM market_derived_metrics
        """)
        row = cur.fetchone()
        return dict(row) if row else {}


def audit_raw_payload_availability(conn) -> Dict:
    """Check if raw_payload exists and contains order book data."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if raw_payload column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'market_book_snapshots' 
              AND column_name = 'raw_payload'
        """)
        has_raw_payload_col = cur.fetchone() is not None
        
        if not has_raw_payload_col:
            return {
                "has_raw_payload_column": False,
                "snapshots_with_raw_payload": 0,
                "sample_has_runners": False,
                "sample_has_atb_atl": False,
            }
        
        # Count snapshots with raw_payload
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM market_book_snapshots
            WHERE raw_payload IS NOT NULL
        """)
        count_row = cur.fetchone()
        snapshots_with_raw = count_row["count"] if count_row else 0
        
        # Sample check: does raw_payload contain runners with availableToBack/availableToLay?
        cur.execute("""
            SELECT raw_payload
            FROM market_book_snapshots
            WHERE raw_payload IS NOT NULL
            LIMIT 10
        """)
        samples = cur.fetchall()
        
        sample_has_runners = False
        sample_has_atb_atl = False
        
        for sample_row in samples:
            try:
                payload = sample_row["raw_payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                
                if isinstance(payload, dict) and "runners" in payload:
                    sample_has_runners = True
                    runners = payload.get("runners", [])
                    if runners:
                        runner = runners[0]
                        if isinstance(runner, dict):
                            ex = runner.get("ex", {})
                            if isinstance(ex, dict):
                                if "availableToBack" in ex or "available_to_back" in ex:
                                    sample_has_atb_atl = True
                                    break
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        
        return {
            "has_raw_payload_column": True,
            "snapshots_with_raw_payload": snapshots_with_raw,
            "sample_has_runners": sample_has_runners,
            "sample_has_atb_atl": sample_has_atb_atl,
        }


def audit_null_percentages(conn) -> Dict:
    """B) NULL percentages for all new parameters."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT 
                COUNT(*) AS total_rows,
                -- Impedance inputs (VWAP/top-N)
                SUM(CASE WHEN home_back_stake IS NULL THEN 1 ELSE 0 END) AS home_back_stake_nulls,
                SUM(CASE WHEN away_back_stake IS NULL THEN 1 ELSE 0 END) AS away_back_stake_nulls,
                SUM(CASE WHEN draw_back_stake IS NULL THEN 1 ELSE 0 END) AS draw_back_stake_nulls,
                SUM(CASE WHEN home_lay_stake IS NULL THEN 1 ELSE 0 END) AS home_lay_stake_nulls,
                SUM(CASE WHEN away_lay_stake IS NULL THEN 1 ELSE 0 END) AS away_lay_stake_nulls,
                SUM(CASE WHEN draw_lay_stake IS NULL THEN 1 ELSE 0 END) AS draw_lay_stake_nulls,
                SUM(CASE WHEN home_back_odds IS NULL THEN 1 ELSE 0 END) AS home_back_odds_nulls,
                SUM(CASE WHEN away_back_odds IS NULL THEN 1 ELSE 0 END) AS away_back_odds_nulls,
                SUM(CASE WHEN draw_back_odds IS NULL THEN 1 ELSE 0 END) AS draw_back_odds_nulls,
                SUM(CASE WHEN home_lay_odds IS NULL THEN 1 ELSE 0 END) AS home_lay_odds_nulls,
                SUM(CASE WHEN away_lay_odds IS NULL THEN 1 ELSE 0 END) AS away_lay_odds_nulls,
                SUM(CASE WHEN draw_lay_odds IS NULL THEN 1 ELSE 0 END) AS draw_lay_odds_nulls,
                -- L1 sizes
                SUM(CASE WHEN home_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS home_best_back_size_l1_nulls,
                SUM(CASE WHEN away_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS away_best_back_size_l1_nulls,
                SUM(CASE WHEN draw_best_back_size_l1 IS NULL THEN 1 ELSE 0 END) AS draw_best_back_size_l1_nulls,
                SUM(CASE WHEN home_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS home_best_lay_size_l1_nulls,
                SUM(CASE WHEN away_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS away_best_lay_size_l1_nulls,
                SUM(CASE WHEN draw_best_lay_size_l1 IS NULL THEN 1 ELSE 0 END) AS draw_best_lay_size_l1_nulls,
                -- Impedance (raw)
                SUM(CASE WHEN home_impedance IS NULL THEN 1 ELSE 0 END) AS home_impedance_nulls,
                SUM(CASE WHEN away_impedance IS NULL THEN 1 ELSE 0 END) AS away_impedance_nulls,
                SUM(CASE WHEN draw_impedance IS NULL THEN 1 ELSE 0 END) AS draw_impedance_nulls,
                -- Risk (imbalance)
                SUM(CASE WHEN home_risk IS NULL THEN 1 ELSE 0 END) AS home_risk_nulls,
                SUM(CASE WHEN away_risk IS NULL THEN 1 ELSE 0 END) AS away_risk_nulls,
                SUM(CASE WHEN draw_risk IS NULL THEN 1 ELSE 0 END) AS draw_risk_nulls
            FROM market_derived_metrics
        """)
        row = cur.fetchone()
        return dict(row) if row else {}


def determine_reconstructability(raw_audit: Dict) -> Dict[str, str]:
    """
    Determine reconstructability based on raw_payload availability.
    Returns eligibility: "Tier A", "Tier B", "Tier C", or "N/A" (already populated).
    """
    has_raw = raw_audit.get("has_raw_payload_column", False)
    has_runners = raw_audit.get("sample_has_runners", False)
    has_atb_atl = raw_audit.get("sample_has_atb_atl", False)
    
    if not has_raw or not has_runners:
        return "Tier C (no raw_payload)"
    
    if has_atb_atl:
        return "Tier A (full reconstruction)"
    else:
        return "Tier B (partial - only if best prices/sizes exist)"


def build_eligibility_matrix(conn, nulls: Dict, raw_audit: Dict) -> list:
    """Build the eligibility matrix."""
    total = nulls.get("total_rows", 0)
    if total == 0:
        return []
    
    matrix = []
    
    # Impedance inputs (VWAP/top-N)
    for outcome in ["home", "away", "draw"]:
        for param in ["back_stake", "lay_stake", "back_odds", "lay_odds"]:
            col = f"{outcome}_{param}"
            null_count = nulls.get(f"{outcome}_{param}_nulls", 0)
            pct_null = (null_count / total * 100) if total > 0 else 0
            populated = total - null_count
            
            # Reconstructability: Tier A if raw_payload has full order book
            if raw_audit.get("sample_has_atb_atl", False):
                reconstructable = "Tier A (full order book in raw_payload)"
            else:
                reconstructable = "Tier C (requires full order book)"
            
            matrix.append({
                "Parameter": col,
                "Populated": populated,
                "NULL": null_count,
                "% NULL": f"{pct_null:.1f}%",
                "Reconstructable": reconstructable,
            })
    
    # L1 sizes
    for outcome in ["home", "away", "draw"]:
        for side in ["back", "lay"]:
            col = f"{outcome}_best_{side}_size_l1"
            null_count = nulls.get(f"{col}_nulls", 0)
            pct_null = (null_count / total * 100) if total > 0 else 0
            populated = total - null_count
            
            # L1 sizes can be reconstructed if raw_payload has at least best-level data
            if raw_audit.get("sample_has_atb_atl", False):
                reconstructable = "Tier A (full order book)"
            elif raw_audit.get("has_raw_payload_column", False):
                reconstructable = "Tier B (check if best prices/sizes exist)"
            else:
                reconstructable = "Tier C (no raw_payload)"
            
            matrix.append({
                "Parameter": col,
                "Populated": populated,
                "NULL": null_count,
                "% NULL": f"{pct_null:.1f}%",
                "Reconstructable": reconstructable,
            })
    
    # Impedance (raw)
    for outcome in ["home", "away", "draw"]:
        col = f"{outcome}_impedance"
        null_count = nulls.get(f"{outcome}_impedance_nulls", 0)
        pct_null = (null_count / total * 100) if total > 0 else 0
        populated = total - null_count
        
        if raw_audit.get("sample_has_atb_atl", False):
            reconstructable = "Tier A (full order book)"
        else:
            reconstructable = "Tier C (requires full order book for VWAP)"
        
        matrix.append({
            "Parameter": col,
            "Populated": populated,
            "NULL": null_count,
            "% NULL": f"{pct_null:.1f}%",
            "Reconstructable": reconstructable,
        })
    
    # Risk (imbalance)
    for outcome in ["home", "away", "draw"]:
        col = f"{outcome}_risk"
        null_count = nulls.get(f"{outcome}_risk_nulls", 0)
        pct_null = (null_count / total * 100) if total > 0 else 0
        populated = total - null_count
        
        if raw_audit.get("sample_has_atb_atl", False):
            reconstructable = "Tier A (full order book)"
        else:
            reconstructable = "Tier C (requires full order book)"
        
        matrix.append({
            "Parameter": col,
            "Populated": populated,
            "NULL": null_count,
            "% NULL": f"{pct_null:.1f}%",
            "Reconstructable": reconstructable,
        })
    
    return matrix


def print_report(counts: Dict, raw_audit: Dict, nulls: Dict, matrix: list):
    """Print formatted audit report."""
    print("=" * 80)
    print("SNAPSHOT INVENTORY AUDIT REPORT")
    print("=" * 80)
    print()
    
    print("A) SNAPSHOT INVENTORY")
    print("-" * 80)
    print(f"Total snapshots: {counts.get('total_snapshots', 0):,}")
    print(f"Oldest snapshot: {counts.get('oldest_snapshot', 'N/A')}")
    print(f"Latest snapshot:  {counts.get('latest_snapshot', 'N/A')}")
    print()
    
    print("B) RAW PAYLOAD AVAILABILITY")
    print("-" * 80)
    print(f"raw_payload column exists: {raw_audit.get('has_raw_payload_column', False)}")
    print(f"Snapshots with raw_payload: {raw_audit.get('snapshots_with_raw_payload', 0):,}")
    print(f"Sample has runners: {raw_audit.get('sample_has_runners', False)}")
    print(f"Sample has availableToBack/availableToLay: {raw_audit.get('sample_has_atb_atl', False)}")
    print()
    
    print("C) NULL PERCENTAGES SUMMARY")
    print("-" * 80)
    total = nulls.get("total_rows", 0)
    if total > 0:
        print(f"Total rows: {total:,}")
        print()
        print("Impedance inputs (VWAP/top-N):")
        for outcome in ["home", "away", "draw"]:
            for param in ["back_stake", "lay_stake"]:
                col = f"{outcome}_{param}"
                null_count = nulls.get(f"{col}_nulls", 0)
                pct = (null_count / total * 100) if total > 0 else 0
                print(f"  {col}: {null_count:,} NULL ({pct:.1f}%)")
        print()
        print("L1 sizes:")
        for outcome in ["home", "away", "draw"]:
            for side in ["back", "lay"]:
                col = f"{outcome}_best_{side}_size_l1"
                null_count = nulls.get(f"{col}_nulls", 0)
                pct = (null_count / total * 100) if total > 0 else 0
                print(f"  {col}: {null_count:,} NULL ({pct:.1f}%)")
        print()
        print("Impedance (raw):")
        for outcome in ["home", "away", "draw"]:
            null_count = nulls.get(f"{outcome}_impedance_nulls", 0)
            pct = (null_count / total * 100) if total > 0 else 0
            print(f"  {outcome}_impedance: {null_count:,} NULL ({pct:.1f}%)")
        print()
        print("Risk (imbalance):")
        for outcome in ["home", "away", "draw"]:
            null_count = nulls.get(f"{outcome}_risk_nulls", 0)
            pct = (null_count / total * 100) if total > 0 else 0
            print(f"  {outcome}_risk: {null_count:,} NULL ({pct:.1f}%)")
    print()
    
    print("D) ELIGIBILITY MATRIX")
    print("-" * 80)
    print(f"{'Parameter':<40} {'Populated':>12} {'NULL':>12} {'% NULL':>10} {'Reconstructable':<50}")
    print("-" * 80)
    for row in matrix:
        print(f"{row['Parameter']:<40} {row['Populated']:>12,} {row['NULL']:>12,} {row['% NULL']:>10} {row['Reconstructable']:<50}")
    print()


def main():
    """Main audit execution."""
    try:
        conn = get_conn()
        
        print("Running snapshot inventory audit...")
        print()
        
        counts = audit_snapshot_counts(conn)
        raw_audit = audit_raw_payload_availability(conn)
        nulls = audit_null_percentages(conn)
        matrix = build_eligibility_matrix(conn, nulls, raw_audit)
        
        print_report(counts, raw_audit, nulls, matrix)
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"ERROR: Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
