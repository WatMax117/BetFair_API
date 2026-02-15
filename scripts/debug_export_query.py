#!/usr/bin/env python3
"""Debug: test export query as rest_writer."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.environ.get("POSTGRES_HOST", "netbet-postgres"),
    dbname=os.environ.get("POSTGRES_DB", "netbet"),
    user=os.environ.get("POSTGRES_USER", "netbet_rest_writer"),
    password=os.environ.get("POSTGRES_PASSWORD", ""),
    options="-c search_path=public",
)
cur = conn.cursor()
# Count raw
cur.execute("SELECT COUNT(*) FROM market_derived_metrics WHERE snapshot_at >= %s AND snapshot_at < %s", ("2026-02-06", "2026-02-08"))
print("Raw market_derived_metrics in range:", cur.fetchone()[0])
# Count with join
cur.execute("""
    SELECT COUNT(*) FROM market_derived_metrics d
    JOIN market_event_metadata e ON e.market_id = d.market_id
    WHERE d.snapshot_at >= %s AND d.snapshot_at < %s
    AND e.home_selection_id IS NOT NULL AND e.away_selection_id IS NOT NULL AND e.draw_selection_id IS NOT NULL
""", ("2026-02-06", "2026-02-08"))
print("With metadata join (H/A/D not null):", cur.fetchone()[0])
# Sample market_ids in range
cur.execute("SELECT DISTINCT d.market_id FROM market_derived_metrics d JOIN market_event_metadata e ON e.market_id = d.market_id WHERE d.snapshot_at >= %s AND d.snapshot_at < %s AND e.home_selection_id IS NOT NULL LIMIT 3", ("2026-02-06", "2026-02-08"))
print("Sample market_ids:", [r[0] for r in cur.fetchall()])
conn.close()
