#!/usr/bin/env python3
"""
Call Betfair Exchange API (Live) for listMarketTypes and listMarketCatalogue.
Outputs raw JSON to verify HALF_TIME_RESULT vs MATCH_ODDS_HT and market type mapping.

Requires: session token from auth-service (BETFAIR_TOKEN_URL) or set BETFAIR_SESSION_TOKEN.
Usage: python scripts/betfair_list_market_types_live.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

TOKEN_URL = os.getenv("BETFAIR_TOKEN_URL", "http://localhost:8080/token")
SESSION_TOKEN = os.getenv("BETFAIR_SESSION_TOKEN", "")
API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
APP_KEY = os.getenv("BETFAIR_APP_KEY", "WftFC5jIOJMsORVD")


def api_call(token: str, method: str, params: dict) -> dict:
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
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
        if "error" in out:
            raise urllib.error.HTTPError(
                req.full_url, 400,
                out["error"].get("message", "API error"), {}, None
            )
        return out.get("result")


def fetch_token() -> str:
    if SESSION_TOKEN:
        return SESSION_TOKEN.strip()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL), timeout=10) as r:
        data = json.load(r)
        token = data.get("ssoid")
        if not token:
            raise SystemExit("No ssoid in token response")
        return token


def main():
    out = {
        "1_listMarketTypes_soccer": None,
        "2_listMarketTypes_event": None,
        "3_listMarketCatalogue_event": None,
        "3_extract_marketId_marketName_marketType_totalMatched": None,
        "eventId_used": None,
    }
    print("Fetching session token...", file=sys.stderr)
    try:
        token = fetch_token()
    except Exception as e:
        print(f"Token fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    # --- 1. listMarketTypes for Soccer (eventTypeIds = [1], locale = "en") ---
    print("1. listMarketTypes (eventTypeIds=[1], locale='en')...", file=sys.stderr)
    try:
        out["1_listMarketTypes_soccer"] = api_call(token, "SportsAPING/v1.0/listMarketTypes", {
            "filter": {"eventTypeIds": ["1"]},
            "locale": "en",
        })
    except urllib.error.HTTPError as e:
        out["1_listMarketTypes_soccer"] = {"_error": str(e), "detail": e.read().decode() if e.fp else ""}
        print(out["1_listMarketTypes_soccer"], file=sys.stderr)
        sys.exit(1)

    # --- Get one active Soccer event for (2) and (3) ---
    print("Resolving one Soccer event...", file=sys.stderr)
    try:
        events_result = api_call(token, "SportsAPING/v1.0/listEvents", {
            "filter": {"eventTypeIds": ["1"]},
            "locale": "en",
        })
    except urllib.error.HTTPError:
        try:
            cat = api_call(token, "SportsAPING/v1.0/listMarketCatalogue", {
                "filter": {"eventTypeIds": ["1"], "inPlayOnly": False},
                "marketProjection": ["EVENT"],
                "sort": "FIRST_TO_START",
                "maxResults": 10,
                "locale": "en",
            })
            if not cat:
                print("No markets returned for event discovery", file=sys.stderr)
                sys.exit(1)
            first = cat[0]
            event_id = (first.get("event") or {}).get("id") or (first.get("market") or {}).get("eventId")
            if not event_id:
                event_id = str((first.get("marketDefinition") or {}).get("eventId", ""))
        except Exception as e:
            print(f"Event discovery failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if not events_result:
            print("No events returned", file=sys.stderr)
            sys.exit(1)
        event_id = str(events_result[0].get("event", {}).get("id", ""))

    if not event_id:
        print("Could not resolve event ID", file=sys.stderr)
        sys.exit(1)
    out["eventId_used"] = event_id
    print(f"eventId: {event_id}", file=sys.stderr)

    # --- 2. listMarketTypes for one Soccer event ---
    print("2. listMarketTypes (eventIds=[...])...", file=sys.stderr)
    try:
        out["2_listMarketTypes_event"] = api_call(token, "SportsAPING/v1.0/listMarketTypes", {
            "filter": {"eventIds": [event_id]},
            "locale": "en",
        })
    except urllib.error.HTTPError as e:
        out["2_listMarketTypes_event"] = {"_error": str(e)}

    # --- 3. listMarketCatalogue for same event (MARKET_DESCRIPTION) ---
    print("3. listMarketCatalogue (MARKET_DESCRIPTION)...", file=sys.stderr)
    try:
        result3 = api_call(token, "SportsAPING/v1.0/listMarketCatalogue", {
            "filter": {"eventIds": [event_id]},
            "marketProjection": ["MARKET_DESCRIPTION"],
            "maxResults": 100,
            "locale": "en",
        })
        out["3_listMarketCatalogue_event"] = result3
        extract = []
        for m in (result3 or []):
            md = m.get("market") or m.get("marketDefinition") or m.get("description") or {}
            mid = m.get("marketId") or m.get("id") or md.get("marketId")
            name = m.get("marketName") or md.get("marketName")
            mtype = (md.get("marketType") if isinstance(md, dict) else None) or m.get("marketType")
            total = m.get("totalMatched") if m.get("totalMatched") is not None else md.get("totalMatched")
            extract.append({"marketId": mid, "marketName": name, "marketType": mtype, "totalMatched": total})
        out["3_extract_marketId_marketName_marketType_totalMatched"] = extract
    except urllib.error.HTTPError as e:
        out["3_listMarketCatalogue_event"] = {"_error": str(e)}
        out["3_extract_marketId_marketName_marketType_totalMatched"] = []

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
