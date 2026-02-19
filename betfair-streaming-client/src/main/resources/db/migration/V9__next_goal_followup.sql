-- V9: NEXT_GOAL follow-up tracking for discovery_hourly.py.
-- Events without NEXT_GOAL at kickoff get one REST check 117s after kickoff.
-- This table tracks attempts (idempotency, reschedule when kickoff postponed).

CREATE TABLE IF NOT EXISTS public.next_goal_followup (
    event_id       VARCHAR(32) PRIMARY KEY,
    kickoff_at     TIMESTAMPTZ,
    followup_at    TIMESTAMPTZ NOT NULL,
    attempted_at   TIMESTAMPTZ NOT NULL,
    found          BOOLEAN NOT NULL,
    market_ids     TEXT[]
);
