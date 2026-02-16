# Streaming Client Schema Fix - Deployment Guide

## Problem

Streaming client was writing to `public.ladder_levels` (which has no partition for today) instead of `stream_ingest.ladder_levels` (which has full partition coverage). This caused all inserts to fail with "no partition found" errors.

## Solution

**1. Code fix:** Schema-qualified all INSERT/UPDATE statements in `PostgresStreamEventSink.java`:
- `ladder_levels` → `stream_ingest.ladder_levels`
- `traded_volume` → `stream_ingest.traded_volume`
- `market_lifecycle_events` → `stream_ingest.market_lifecycle_events`
- `market_liquidity_history` → `stream_ingest.market_liquidity_history`
- `markets` → `public.markets` (metadata table, remains in public)

**2. DB lock-down:** Revoke write privileges on `public.ladder_levels` from streaming client user to prevent accidental writes.

## Deployment Steps

### Step 1: Deploy code fix

```bash
# On VPS
cd /opt/netbet
docker compose build streaming-client
docker compose up -d --no-deps streaming-client
```

### Step 2: Verify writes go to stream_ingest

Wait 2-3 minutes for streaming client to start writing, then run:

```bash
cat /opt/netbet/scripts/verify_streaming_writes.sql | docker exec -i netbet-postgres psql -U netbet -d netbet
```

**Expected:**
- `stream_ingest.ladder_levels`: count > 0 for today, max_ts advances
- `public.ladder_levels`: count = 0 for today (or max_ts does not advance)

### Step 3: Check streaming client logs

```bash
docker logs netbet-streaming-client --tail 50 2>&1 | grep -i -E 'error|exception|flush|insert'
```

**Expected:** No "no partition found" errors. Successful flush messages.

### Step 4: Apply DB lock-down (after verification)

Once confirmed that writes go to `stream_ingest.ladder_levels`:

```bash
cat /opt/netbet/scripts/lockdown_public_ladder_levels.sql | docker exec -i netbet-postgres psql -U netbet -d netbet -v ON_ERROR_STOP=1
```

### Step 5: Verify API/UI

- `/api/stream/events/by-date-snapshots?date=<today>` should return non-empty (once data exists)
- `/stream` UI should show events and charts for today

## Verification Checklist

- [ ] Streaming client restarted successfully
- [ ] No "no partition found" errors in logs
- [ ] `stream_ingest.ladder_levels` has rows for today
- [ ] `public.ladder_levels` has no new rows for today
- [ ] API returns events for today
- [ ] UI displays today's events
- [ ] DB lock-down applied (write privileges revoked)

## Cleanup (after 24h stable operation)

After system runs stably for at least one day:

```sql
-- Rename public.ladder_levels to prevent accidental writes
ALTER TABLE public.ladder_levels RENAME TO ladder_levels_deprecated;
```

Then later (after another stable period) drop it if confirmed unused.
