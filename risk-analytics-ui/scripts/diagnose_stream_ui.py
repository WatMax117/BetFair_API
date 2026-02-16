#!/usr/bin/env python3
"""
Diagnostics for /stream UI: DB freshness, metadata join, timezone, optional API checks.
Run from repo root with PYTHONPATH including risk-analytics-ui/api, or from risk-analytics-ui/api as:
  python -m scripts.diagnose_stream_ui [--api-base http://localhost:8000]
"""
import argparse
import os
import sys
from datetime import datetime, timezone

# Ensure api/app is importable (script lives in risk-analytics-ui/scripts/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_api_dir = os.path.join(_script_dir, "..", "api")
sys.path.insert(0, os.path.abspath(_api_dir))

from app.db import cursor


def run_query(cur, sql: str, params=None, label: str = ""):
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    return rows


def main():
    ap = argparse.ArgumentParser(description="Stream UI diagnostics")
    ap.add_argument("--api-base", default="", help="e.g. http://localhost:8000 to hit /stream/... and report status codes")
    args = ap.parse_args()

    print("=" * 60)
    print("STREAM UI DIAGNOSTICS")
    print("=" * 60)

    # --- 2. Streaming data freshness ---
    print("\n## 2. Streaming data freshness (stream_ingest.ladder_levels)")
    try:
        with cursor() as cur:
            cur.execute("""
                SELECT max(publish_time) AS last_publish_time
                FROM stream_ingest.ladder_levels
            """)
            row = cur.fetchone()
            last_pt = row["last_publish_time"] if row else None
            print(f"  last_publish_time: {last_pt}")

            cur.execute("""
                SELECT count(*) AS rows_last_60m
                FROM stream_ingest.ladder_levels
                WHERE publish_time > now() - interval '60 minutes'
            """)
            row = cur.fetchone()
            rows_60m = row["rows_last_60m"] if row else 0
            print(f"  rows_last_60m:     {rows_60m}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # --- 4. Metadata join ---
    print("\n## 4. Metadata join (ladder markets without public.market_event_metadata)")
    try:
        with cursor() as cur:
            cur.execute("""
                SELECT ll.market_id
                FROM (
                    SELECT DISTINCT market_id
                    FROM stream_ingest.ladder_levels
                    WHERE publish_time > now() - interval '6 hours'
                ) ll
                LEFT JOIN public.market_event_metadata m ON m.market_id = ll.market_id
                WHERE m.market_id IS NULL
                LIMIT 20
            """)
            rows = cur.fetchall()
            if not rows:
                print("  (none) — all ladder markets have metadata")
            else:
                for r in rows:
                    print(f"  missing metadata: {r['market_id']}")
                print(f"  total: {len(rows)} markets")
    except Exception as e:
        print(f"  ERROR: {e}")

    # --- 5. Timezone ---
    print("\n## 5. Timezone consistency")
    try:
        with cursor() as cur:
            cur.execute("""
                SELECT
                    now() AS server_time,
                    now() AT TIME ZONE 'utc' AS utc_time,
                    max(publish_time) AS last_publish_time
                FROM stream_ingest.ladder_levels
            """)
            row = cur.fetchone()
            if row:
                print(f"  server_time:      {row['server_time']}")
                print(f"  utc_time:        {row['utc_time']}")
                print(f"  last_publish_time: {row['last_publish_time']}")
            else:
                print("  (no ladder rows)")
    except Exception as e:
        print(f"  ERROR: {e}")

    # --- 1. API routing (optional) ---
    if args.api_base:
        base = args.api_base.rstrip("/")
        print("\n## 1. API status (stream endpoints)")
        import urllib.request
        import urllib.error
        import json

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        endpoints = [
            ("/stream/events/by-date-snapshots", f"{base}/stream/events/by-date-snapshots?date={today}"),
            ("/stream/events/{id}/meta", None),  # need a real market_id
        ]
        for name, url in endpoints:
            if not url:
                continue
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    code = resp.getcode()
                    body = resp.read().decode()
                    try:
                        data = json.loads(body)
                        size = len(data) if isinstance(data, list) else "(object)"
                    except Exception:
                        size = len(body)
                    print(f"  {name}: {code} (response: {size})")
            except urllib.error.HTTPError as e:
                print(f"  {name}: {e.code} {e.reason}")
            except Exception as e:
                print(f"  {name}: ERROR {e}")
        # If by-date-snapshots returned events, probe timeseries and meta for first market
        try:
            url = f"{base}/stream/events/by-date-snapshots?date={today}"
            with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list) and len(data) > 0:
                    mid = data[0].get("market_id")
                    if mid:
                        try:
                            r = urllib.request.urlopen(urllib.request.Request(f"{base}/stream/events/{mid}/timeseries?interval_minutes=15"), timeout=10)
                            print(f"  /stream/events/{{id}}/timeseries: {r.getcode()}")
                        except Exception as ex:
                            print(f"  /stream/events/{{id}}/timeseries: {ex}")
                        try:
                            r = urllib.request.urlopen(urllib.request.Request(f"{base}/stream/events/{mid}/meta"), timeout=10)
                            print(f"  /stream/events/{{id}}/meta:        {r.getcode()}")
                        except Exception as ex:
                            print(f"  /stream/events/{{id}}/meta:        {ex}")
        except Exception as e:
            print(f"  (could not probe timeseries/meta: {e})")
    else:
        print("\n## 1. API routing")
        print("  (run with --api-base http://localhost:8000 to check status codes)")

    print("\n" + "=" * 60)
    print("STALE_MINUTES is in api/app/stream_data.py; current value is applied after backend restart.")
    print("=" * 60)


if __name__ == "__main__":
    main()
