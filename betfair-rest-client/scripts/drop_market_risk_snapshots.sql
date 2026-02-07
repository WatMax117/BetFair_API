-- Clean deployment: drop market_risk_snapshots so the daemon can recreate it with raw_payload (JSONB).
-- Run on VPS: docker exec -i netbet-postgres psql -U netbet -d netbet -f - < drop_market_risk_snapshots.sql

DROP TABLE IF EXISTS market_risk_snapshots;
