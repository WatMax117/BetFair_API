package com.netbet.streaming.subscription;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

/**
 * Reads market IDs to stream from the DB view active_markets_to_stream (populated by REST discovery).
 * Full-Time only: MATCH_ODDS_FT, OVER_UNDER_25_FT, NEXT_GOAL (no Half-Time).
 * Used when betfair.subscribe-from-db is true; otherwise subscription uses priority resolver or config list.
 * No subscription cap: all rows from the view are used. List is split into batches for submission (subscription-batch-size).
 */
@Component
public class ActiveMarketsFromDb {

    private static final Logger log = LoggerFactory.getLogger(ActiveMarketsFromDb.class);
    /** Legacy: Betfair stream API limit per message ~200; use subscriptionBatchSize for batching. */
    @Deprecated
    public static final int MAX_MARKET_IDS_PER_SUBSCRIPTION = 200;

    private static final String SQL_SELECT_MARKET_IDS =
            "SELECT market_id FROM public.active_markets_to_stream ORDER BY market_id";

    private final JdbcTemplate jdbc;
    /** Max markets per subscription message (batch size, default 177). */
    private final int subscriptionBatchSize;

    public ActiveMarketsFromDb(JdbcTemplate jdbc,
                              @Value("${betfair.subscription-batch-size:177}") int subscriptionBatchSize) {
        this.jdbc = jdbc;
        this.subscriptionBatchSize = Math.max(1, Math.min(200, subscriptionBatchSize));
    }

    /** Max market IDs per subscription message (batch size cap). */
    public int getSubscriptionBatchSize() {
        return subscriptionBatchSize;
    }

    /**
     * Load market IDs from active_markets_to_stream. Returns the full list (ORDER BY market_id); no cap.
     * Caller batches the result with {@link #batch(List, int)} using getSubscriptionBatchSize().
     */
    public List<String> loadActiveMarketIds() {
        try {
            List<String> ids = jdbc.query(SQL_SELECT_MARKET_IDS, (rs, rowNum) -> rs.getString("market_id"));
            ids = ids != null ? ids : Collections.emptyList();
            log.info("Loaded {} market IDs from active_markets_to_stream (FT only)", ids.size());
            // DIAG: confirm selected list and presence of diagnostic market (1.254212094)
            String diagMarket = "1.254212094";
            List<String> first10 = ids.size() <= 10 ? ids : ids.subList(0, 10);
            log.info("DIAG Selected {} markets for subscription; first10={}; contains_{}={}",
                    ids.size(), first10, diagMarket.replace(".", "_"), ids.contains(diagMarket));
            return ids;
        } catch (Exception e) {
            log.warn("Failed to load active_markets_to_stream: {}. Subscription will use config or priority.", e.getMessage());
            return Collections.emptyList();
        }
    }

    /**
     * Split list into batches of at most maxPerBatch for multiple subscription messages (one per batch on same connection).
     */
    public static List<List<String>> batch(List<String> marketIds, int maxPerBatch) {
        if (marketIds == null || marketIds.isEmpty()) return Collections.emptyList();
        int size = Math.max(1, maxPerBatch);
        return java.util.stream.IntStream.range(0, (marketIds.size() + size - 1) / size)
                .mapToObj(i -> marketIds.subList(i * size, Math.min((i + 1) * size, marketIds.size())))
                .toList();
    }
}
