-- Phase 6: Confirm whether CLOSED status exists in DB (global check).
-- Run on VPS: docker exec netbet-postgres psql -U netbet -d netbet -f - < scripts/check_closed_status.sql
-- Or: psql -U netbet -d netbet -v ON_ERROR_STOP=1 -f scripts/check_closed_status.sql

\echo '=== market_book_snapshots: count by status ==='
SELECT status, COUNT(*) AS cnt
FROM market_book_snapshots
GROUP BY status
ORDER BY cnt DESC;

\echo ''
\echo '=== Total rows with status = CLOSED ==='
SELECT COUNT(*) AS closed_count
FROM market_book_snapshots
WHERE status = 'CLOSED';

\echo ''
\echo '=== Sample of distinct status values ==='
SELECT DISTINCT status FROM market_book_snapshots LIMIT 20;
