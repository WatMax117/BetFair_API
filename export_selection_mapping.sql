-- Selection mapping export: market_id -> home/away/draw selection_ids
-- For later use in mapping raw exports to outcomes

SELECT
  market_id,
  home_selection_id,
  away_selection_id,
  draw_selection_id
FROM public.market_event_metadata
WHERE home_selection_id IS NOT NULL
  AND away_selection_id IS NOT NULL
  AND draw_selection_id IS NOT NULL
ORDER BY market_id;
