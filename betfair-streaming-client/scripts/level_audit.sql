-- Level audit: uses today's partition (run from VPS with date substitution or edit table name)
-- Example: ladder_levels_20260205
SELECT level, COUNT(*) FROM ladder_levels_20260205 GROUP BY level ORDER BY level;
