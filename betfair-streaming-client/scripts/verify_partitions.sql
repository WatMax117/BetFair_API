-- NetBet Betfair Streaming – Verify ladder_levels partitioning (run with psql).
-- Usage: psql -U netbet -d netbet -f scripts/verify_partitions.sql

-- Parent table definition
\d+ ladder_levels

-- List all partitions and their range bounds (from pg_inherits + relpartbound)
SELECT
    c.relname AS partition_name,
    pg_get_expr(c.relpartbound, c.oid) AS range_bounds
FROM pg_inherits i
JOIN pg_class p ON p.oid = i.inhparent
JOIN pg_class c ON c.oid = i.inhrelid
WHERE p.relname = 'ladder_levels'
ORDER BY c.relname;
