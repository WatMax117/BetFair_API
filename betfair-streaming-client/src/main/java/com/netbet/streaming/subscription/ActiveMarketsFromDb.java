package com.netbet.streaming.subscription;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Reads market IDs to stream from the DB view active_markets_to_stream (populated by REST discovery).
 * Full-Time only: MATCH_ODDS_FT, OVER_UNDER_25_FT, NEXT_GOAL (no Half-Time).
 * Used when betfair.subscribe-from-db is true; otherwise subscription uses priority resolver or config list.
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
    /** Max markets per subscription message (safety cap, default 177). */
    private final int subscriptionBatchSize;
    /** Optional limit for reduced-set experiment. 0 = no limit (subscribe to all eligible). */
    private final int subscriptionLimit;
    /** Priority market IDs always included when limit is applied (e.g. for diag). */
    private final Set<String> priorityMarketIds;

    public ActiveMarketsFromDb(JdbcTemplate jdbc,
                              @Value("${betfair.subscription-batch-size:177}") int subscriptionBatchSize,
                              @Value("${betfair.subscription-limit:0}") int subscriptionLimit,
                              @Value("${betfair.subscription-priority-market-ids:}") String priorityMarketIdsCsv) {
        this.jdbc = jdbc;
        this.subscriptionBatchSize = Math.max(1, Math.min(200, subscriptionBatchSize));
        this.subscriptionLimit = Math.max(0, subscriptionLimit);
        this.priorityMarketIds = parsePriorityIds(priorityMarketIdsCsv);
    }

    /** Max market IDs per subscription message (batch size cap). */
    public int getSubscriptionBatchSize() {
        return subscriptionBatchSize;
    }

    private static Set<String> parsePriorityIds(String csv) {
        if (csv == null || csv.isBlank()) return Set.of();
        return java.util.Arrays.stream(csv.split(",\\s*"))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toSet());
    }

    /**
     * Load market IDs from active_markets_to_stream. When subscription-limit > 0, returns at most that many,
     * with priority-market-ids included first. Used for reduced-set experiments.
     */
    public List<String> loadActiveMarketIds() {
        try {
            List<String> ids = jdbc.query(SQL_SELECT_MARKET_IDS, (rs, rowNum) -> rs.getString("market_id"));
            ids = ids != null ? ids : Collections.emptyList();
            int originalSize = ids.size();

            if (subscriptionLimit > 0 && !ids.isEmpty()) {
                LinkedHashSet<String> result = new LinkedHashSet<>();
                for (String pid : priorityMarketIds) {
                    if (ids.contains(pid)) result.add(pid);
                }
                for (String id : ids) {
                    if (result.size() >= subscriptionLimit) break;
                    result.add(id);
                }
                ids = new ArrayList<>(result);
                log.info("Loaded {} market IDs from active_markets_to_stream (FT only, limit={}, priority={} included)",
                        ids.size(), subscriptionLimit, priorityMarketIds.size());
            } else {
                log.info("Loaded {} market IDs from active_markets_to_stream (FT only)", originalSize);
            }
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
