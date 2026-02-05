-- Step 2: v_golden_audit output parameters
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'v_golden_audit'
ORDER BY ordinal_position;
