#!/usr/bin/env python3
"""
Validate that a given id exists in market_event_metadata (same DB as Risk Analytics API).
Use this to confirm whether a 404 from GET /api/debug/events/{id}/markets is due to
missing data or wrong environment.

Usage:
  From repo root (with same POSTGRES_* env as the API, or .env in api/):
    python risk-analytics-ui/scripts/validate_market_event_id.py [id]
  Example:
    python risk-analytics-ui/scripts/validate_market_event_id.py 1.251575028

  Or from risk-analytics-ui/api with app on PYTHONPATH:
    cd risk-analytics-ui/api && python -c "
from app.db import cursor
id = '1.251575028'
with cursor() as cur:
    cur.execute('SELECT market_id, event_id FROM market_event_metadata WHERE market_id = %s OR event_id = %s', (id, id))
    rows = cur.fetchall()
print('Rows found:', len(rows))
for r in rows: print(r)
"
"""
import os
import sys

# Optional: load .env from api/ if present
_api_dir = os.path.join(os.path.dirname(__file__), "..", "api")
if os.path.isfile(os.path.join(_api_dir, ".env")):
    try:
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_api_dir, ".env"))
    except ImportError:
        pass

import psycopg2
from psycopg2.extras import RealDictCursor

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "netbet")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "netbet")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")


def main():
    id_val = (sys.argv[1] if len(sys.argv) > 1 else "1.251575028").strip()
    if not id_val:
        print("Usage: validate_market_event_id.py [id]")
        sys.exit(1)

    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=10,
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT market_id, event_id
                FROM market_event_metadata
                WHERE market_id = %s OR event_id = %s
                """,
                (id_val, id_val),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"DB: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    print(f"Query: market_id = '{id_val}' OR event_id = '{id_val}'")
    print(f"Rows found: {len(rows)}")
    if rows:
        for r in rows:
            print(f"  market_id={r['market_id']!r}, event_id={r['event_id']!r}")
    else:
        print("  => No rows. 404 from /api/debug/events/{id}/markets is expected.")
        print("  => Either this market was never ingested or the API is using a different DB.")


if __name__ == "__main__":
    main()
