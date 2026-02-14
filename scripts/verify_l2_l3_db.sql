-- Verify L2/L3 columns populated in market_derived_metrics
-- Run on VPS: docker exec netbet-postgres psql -U netbet -d netbet -f - < scripts/verify_l2_l3_db.sql

SELECT snapshot_id, snapshot_at, market_id,
       home_back_odds_l2, home_back_size_l2, home_back_odds_l3, home_back_size_l3,
       away_back_odds_l2, away_back_size_l2, away_back_odds_l3, away_back_size_l3,
       draw_back_odds_l2, draw_back_size_l2, draw_back_odds_l3, draw_back_size_l3
FROM public.market_derived_metrics
ORDER BY snapshot_at DESC
LIMIT 20;
