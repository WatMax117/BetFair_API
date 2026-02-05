#!/usr/bin/env python3
"""
Discover live Football market IDs for streaming (8 market types).
Fetches token from auth service, finds highest-volume in-play match,
returns comma-separated market IDs for: MATCH_ODDS, CORRECT_SCORE, TOTAL_GOALS,
HALF_TIME, HALFTIME_SCORE, OVER_UNDER_05_HT, OVER_UNDER_15_HT, NEXT_GOAL.
"""
import json
import os
import sys
import urllib.request
import urllib.error

TOKEN_URL = os.getenv("BETFAIR_TOKEN_URL", "http://localhost:8080/token")
API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
APP_KEY = os.getenv("BETFAIR_APP_KEY", "WftFC5jIOJMsORVD")

MARKET_TYPES = [
    "MATCH_ODDS", "CORRECT_SCORE", "TOTAL_GOALS", "HALF_TIME",
    "HALFTIME_SCORE", "OVER_UNDER_05_HT", "OVER_UNDER_15_HT", "NEXT_GOAL",
]


def api_call(token, method, params):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Application": APP_KEY,
            "X-Authentication": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
        if "result" in out:
            return out["result"]
        if "error" in out:
            raise urllib.error.HTTPError(req.full_url, 400, out["error"].get("message", "API error"), {}, None)
        return out


def fetch_token():
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL)) as r:
        data = json.load(r)
        token = data.get("ssoid")
        if not token:
            raise SystemExit("No ssoid in token response")
        return token


def list_market_catalogue(token, event_type_ids, market_type_codes, max_results=50):
    return api_call(token, "SportsAPING/v1.0/listMarketCatalogue", {
        "filter": {
            "eventTypeIds": event_type_ids,
            "marketTypeCodes": market_type_codes,
            "turnInPlayEnabled": True,
        },
        "marketProjection": ["MARKET_DESCRIPTION"],
        "sort": "FIRST_TO_START",
        "maxResults": max_results,
    })


def list_market_book(token, market_ids):
    return api_call(token, "SportsAPING/v1.0/listMarketBook", {
        "marketIds": market_ids,
        "priceProjection": {"priceData": ["EX_TRADED"]},
    })


def main():
    try:
        token = fetch_token()
    except urllib.error.HTTPError as e:
        print(f"Token fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Get in-play Match Odds markets
    try:
        match_odds = list_market_catalogue(token, ["1"], ["MATCH_ODDS"])
    except urllib.error.HTTPError as e:
        print(f"listMarketCatalogue failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not match_odds:
        print("No in-play football Match Odds markets", file=sys.stderr)
        sys.exit(1)

    # Filter in-play and get market books for volume
    in_play = [m for m in match_odds if (m.get("market") or {}).get("inPlay") or (m.get("marketDefinition") or {}).get("inPlay")]
    candidates = in_play or match_odds
    market_ids_for_book = [m.get("marketId") or m.get("id") for m in candidates[:20] if m.get("marketId") or m.get("id")]

    if not market_ids_for_book:
        print("No valid market IDs", file=sys.stderr)
        sys.exit(1)

    # 2. Get volume (totalMatched) to find highest
    try:
        books = list_market_book(token, market_ids_for_book)
    except urllib.error.HTTPError:
        books = []
    volume_by_id = {b.get("marketId"): b.get("totalMatched") or 0 for b in (books or [])}
    best = max(candidates, key=lambda m: volume_by_id.get(m.get("marketId") or m.get("id"), 0))
    event_id = (best.get("market") or best.get("marketDefinition") or {}).get("eventId")
    if not event_id:
        event_id = str((best.get("event") or {}).get("id", ""))

    # 3. Get all 8 market types for this event
    try:
        all_markets = list_market_catalogue(token, ["1"], MARKET_TYPES, 100)
    except urllib.error.HTTPError:
        all_markets = []

    def evt(m):
        return (m.get("market") or m.get("marketDefinition") or {}).get("eventId") or str((m.get("event") or {}).get("id", ""))
    event_markets = [m for m in (all_markets or []) if evt(m) == event_id] if event_id else []
    if not event_markets:
        event_markets = candidates

    ids = []
    seen = set()
    for m in event_markets:
        mid = m.get("marketId") or m.get("id")
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(str(mid))

    if not ids:
        ids = [str(best.get("marketId") or best.get("id"))]

    print(",".join(ids))


if __name__ == "__main__":
    main()
