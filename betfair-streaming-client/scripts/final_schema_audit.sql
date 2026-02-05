-- Step 1: Detailed parameter inspection (core tables)
SELECT
    cols.table_name,
    cols.column_name,
    cols.data_type,
    cols.is_nullable,
    (SELECT 'PRIMARY KEY'
     FROM information_schema.table_constraints tc
     JOIN information_schema.key_column_usage kcu
       ON tc.constraint_name = kcu.constraint_name
       AND tc.table_name = kcu.table_name
     WHERE kcu.column_name = cols.column_name
       AND kcu.table_name = cols.table_name
       AND tc.constraint_type = 'PRIMARY KEY') AS key_type
FROM information_schema.columns cols
WHERE cols.table_schema = 'public'
  AND cols.table_name IN ('events', 'markets', 'market_liquidity_history', 'ladder_levels')
ORDER BY cols.table_name, cols.ordinal_position;
