package com.netbet.streaming.subscription;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

/**
 * Reads market IDs to stream from the DB view active_markets_to_stream (populated by REST discovery).
 * Full-Time only: MATCH_ODDS_FT, OVER_UNDER_25_FT, NEXT_GOAL (no Half-Time).
 * Used when betfair.subscribe-from-db is true; otherwise subscription uses priority resolver or config list.
 */
@Component
public class ActiveMarketsFromDb {

    private static final Logger log = LoggerFactory.getLogger(ActiveMarketsFromDb.class);
    /** Betfair stream API limit per marketSubscription message (documented ~200). */
    public static final int MAX_MARKET_IDS_PER_SUBSCRIPTION = 200;

    private static final String SQL_SELECT_MARKET_IDS =
            "SELECT market_id FROM active_markets_to_stream ORDER BY market_id";

    private final JdbcTemplate jdbc;

    public ActiveMarketsFromDb(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Load all market IDs from active_markets_to_stream. Returns empty list on error or if view is empty.
     */
    public List<String> loadActiveMarketIds() {
        try {
            List<String> ids = jdbc.query(SQL_SELECT_MARKET_IDS, (rs, rowNum) -> rs.getString("market_id"));
            log.info("Loaded {} market IDs from active_markets_to_stream (FT only)", ids != null ? ids.size() : 0);
            return ids != null ? ids : Collections.emptyList();
        } catch (Exception e) {
            log.warn("Failed to load active_markets_to_stream: {}. Subscription will use config or priority.", e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * Split list into batches of at most MAX_MARKET_IDS_PER_SUBSCRIPTION for multiple subscription messages.
     */
    public static List<List<String>> batch(List<String> marketIds, int maxPerBatch) {
        if (marketIds == null || marketIds.isEmpty()) return Collections.emptyList();
        int size = Math.max(1, maxPerBatch);
        return java.util.stream.IntStream.range(0, (marketIds.size() + size - 1) / size)
                .mapToObj(i -> marketIds.subList(i * size, Math.min((i + 1) * size, marketIds.size())))
                .toList();
    }
}
