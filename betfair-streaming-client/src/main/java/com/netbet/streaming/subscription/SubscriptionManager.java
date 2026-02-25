package com.netbet.streaming.subscription;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Handles idempotent subscription payloads for the Betfair Stream API.
 * On reconnection, re-issues the exact same filters (soccer-only, 8-level depth).
 * Reference: Betfair Exchange Stream API - Subscription / MarketSubscriptionMessage.
 */
@Component
public class SubscriptionManager {

    private static final Logger log = LoggerFactory.getLogger(SubscriptionManager.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** Full-Time only: Match Odds FT, O/U 2.5 FT, Next Goal. No Half-Time markets. */
    private static final String[] SOCCER_MARKET_TYPES_FT = {
            "MATCH_ODDS_FT", "OVER_UNDER_25_FT", "NEXT_GOAL"
    };

    private static final String[] MARKET_DATA_FIELDS = {
            "EX_ALL_OFFERS", "EX_TRADED_VOL", "EX_TRADED", "EX_LTP", "EX_MARKET_DEF"
    };

    private final String appKey;
    private final int heartbeatMs;
    private final int conflateMs;
    private final int ladderLevels;
    private final List<String> configMarketIds;
    /** Runtime list: market IDs from DB (active_markets_to_stream) or priority/config. Set before first subscribe. */
    private final List<String> priorityMarketIds = new CopyOnWriteArrayList<>();

    /** When non-empty, each sublist is sent as a separate subscription (batch). Max 200 per batch (Betfair limit). */
    private volatile List<List<String>> batchedMarketIds = List.of();

    /** Last subscription id used (for resubscribe we use same criteria, new id optional). */
    private int lastSubscriptionId = 2;

    /** Stored for resubscribe with initialClk/clk when available (faster recovery). */
    private volatile String lastInitialClk;
    private volatile String lastClk;

    public SubscriptionManager(
            @Value("${betfair.app-key}") String appKey,
            @Value("${betfair.heartbeat-ms:5000}") int heartbeatMs,
            @Value("${betfair.conflate-ms:0}") int conflateMs,
            @Value("${betfair.ladder-levels:8}") int ladderLevels,
            @Value("${betfair.market-ids:}") List<String> marketIds,
            @Value("${betfair.market-id:}") String singleMarketId,
            @Value("${BETFAIR_MARKET_IDS:}") String marketIdsCsv) {
        this.appKey = appKey;
        this.heartbeatMs = Math.max(500, Math.min(5000, heartbeatMs));
        this.conflateMs = Math.max(0, conflateMs);
        this.ladderLevels = Math.max(1, Math.min(10, ladderLevels));
        List<String> ids = marketIds != null ? marketIds : Collections.emptyList();
        if (ids.isEmpty() && singleMarketId != null && !singleMarketId.isBlank()) {
            ids = List.of(singleMarketId.trim());
        }
        if (ids.isEmpty() && marketIdsCsv != null && !marketIdsCsv.isBlank()) {
            ids = java.util.Arrays.stream(marketIdsCsv.split(",\\s*")).map(String::trim).filter(s -> !s.isEmpty()).toList();
        }
        this.configMarketIds = ids;
    }

    /** Set market IDs to subscribe to (e.g. from ActiveMarketsFromDb or PriorityMarketResolver). */
    public void setPriorityMarketIds(List<String> ids) {
        priorityMarketIds.clear();
        if (ids != null && !ids.isEmpty()) {
            priorityMarketIds.addAll(ids);
        }
        batchedMarketIds = List.of();
        log.info("Subscription market list set to {} IDs", priorityMarketIds.size());
    }

    /** Set batched market IDs (e.g. from ActiveMarketsFromDb.loadActiveMarketIds() + batch). Each batch sent as separate subscription. */
    public void setBatchedMarketIds(List<List<String>> batches) {
        if (batches != null && !batches.isEmpty()) {
            batchedMarketIds = new CopyOnWriteArrayList<>(batches);
            priorityMarketIds.clear();
            int total = batches.stream().mapToInt(List::size).sum();
            log.info("Subscription set to {} batches, {} total market IDs", batches.size(), total);
        } else {
            batchedMarketIds = List.of();
        }
    }

    /**
     * Builds idempotent market subscription payload. Same criteria every time for re-subscribe.
     * When initialClk/clk are set (after first initial image), pass them for RESUB_DELTA recovery.
     */
    public String buildMarketSubscriptionPayload(int id, String initialClk, String clk) {
        return buildMarketSubscriptionPayloadForIds(id, null, initialClk, clk);
    }

    /** Build one subscription payload for a specific list of market IDs (used for DB-sourced batches). */
    public String buildMarketSubscriptionPayloadForIds(int id, List<String> marketIds, String initialClk, String clk) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("op", "marketSubscription");
        root.put("id", id);
        root.put("heartbeatMs", heartbeatMs);
        root.put("conflateMs", conflateMs);
        if (initialClk != null && !initialClk.isBlank()) {
            root.put("initialClk", initialClk);
        }
        if (clk != null && !clk.isBlank()) {
            root.put("clk", clk);
        }

        ObjectNode marketFilter = MAPPER.createObjectNode();
        List<String> idsToUse = (marketIds != null && !marketIds.isEmpty()) ? marketIds
                : (!priorityMarketIds.isEmpty() ? priorityMarketIds : configMarketIds);
        if (idsToUse != null && !idsToUse.isEmpty()) {
            ArrayNode ids = MAPPER.createArrayNode();
            idsToUse.forEach(ids::add);
            marketFilter.set("marketIds", ids);
        } else {
            ArrayNode eventTypeIds = MAPPER.createArrayNode();
            eventTypeIds.add("1"); // Football
            marketFilter.set("eventTypeIds", eventTypeIds);
            ArrayNode marketTypeCodes = MAPPER.createArrayNode();
            for (String mt : SOCCER_MARKET_TYPES_FT) {
                marketTypeCodes.add(mt);
            }
            marketFilter.set("marketTypeCodes", marketTypeCodes);
        }
        root.set("marketFilter", marketFilter);

        ObjectNode marketDataFilter = MAPPER.createObjectNode();
        marketDataFilter.put("ladderLevels", ladderLevels);
        ArrayNode fields = MAPPER.createArrayNode();
        for (String f : MARKET_DATA_FIELDS) {
            fields.add(f);
        }
        marketDataFilter.set("fields", fields);
        root.set("marketDataFilter", marketDataFilter);

        return root.toString();
    }

    /** Returns subscription payload for initial subscribe (no clk). */
    public String getInitialSubscriptionPayload() {
        lastSubscriptionId = 2;
        lastInitialClk = null;
        lastClk = null;
        return buildMarketSubscriptionPayload(lastSubscriptionId, null, null);
    }

    /** Returns multiple payloads when using DB-sourced batches (one payload per batch, id 2, 3, 4, ...). Otherwise single payload. */
    public List<String> getInitialSubscriptionPayloads() {
        lastSubscriptionId = 2;
        lastInitialClk = null;
        lastClk = null;
        if (batchedMarketIds != null && !batchedMarketIds.isEmpty()) {
            List<String> payloads = new java.util.ArrayList<>();
            int id = 2;
            int batchIndex = 0;
            for (List<String> batch : batchedMarketIds) {
                if (!batch.isEmpty()) {
                    String first = batch.get(0);
                    String last = batch.get(batch.size() - 1);
                    log.info("Subscription batch {}: id={}, size={}, first={}, last={}",
                            batchIndex + 1, id, batch.size(), first, last);
                    payloads.add(buildMarketSubscriptionPayloadForIds(id++, batch, null, null));
                    batchIndex++;
                }
            }
            lastSubscriptionId = id - 1;
            return payloads;
        }
        return List.of(getInitialSubscriptionPayload());
    }

    /** Returns subscription payload for resubscribe; uses stored initialClk/clk when available. */
    public String getResubscribePayload() {
        int id = lastSubscriptionId;
        String ic = lastInitialClk;
        String c = lastClk;
        log.debug("Resubscribe payload id={} initialClk={} clk={}", id, ic != null ? "set" : "null", c != null ? "set" : "null");
        return buildMarketSubscriptionPayload(id, ic, c);
    }

    /** Returns multiple resubscribe payloads when using batches. */
    public List<String> getResubscribePayloads() {
        String ic = lastInitialClk;
        String c = lastClk;
        if (batchedMarketIds != null && !batchedMarketIds.isEmpty()) {
            List<String> payloads = new java.util.ArrayList<>();
            int id = 2;
            int batchIndex = 0;
            for (List<String> batch : batchedMarketIds) {
                if (!batch.isEmpty()) {
                    String first = batch.get(0);
                    String last = batch.get(batch.size() - 1);
                    log.info("Resubscribe batch {}: id={}, size={}, first={}, last={}",
                            batchIndex + 1, id, batch.size(), first, last);
                    payloads.add(buildMarketSubscriptionPayloadForIds(id++, batch, ic, c));
                    batchIndex++;
                }
            }
            return payloads;
        }
        return List.of(getResubscribePayload());
    }

    /** Update stored clock tokens from a change message (mcm). Call from message handler. */
    public void updateClocks(String initialClk, String clk) {
        if (initialClk != null && !initialClk.isBlank()) {
            this.lastInitialClk = initialClk;
        }
        if (clk != null && !clk.isBlank()) {
            this.lastClk = clk;
        }
    }

    public int getLastSubscriptionId() {
        return lastSubscriptionId;
    }

    public int getLadderLevels() {
        return ladderLevels;
    }

    /** Current market IDs (flattened from batchedMarketIds). Used for change detection. */
    public java.util.Set<String> getCurrentMarketIds() {
        if (batchedMarketIds == null || batchedMarketIds.isEmpty()) {
            return java.util.Set.of();
        }
        java.util.Set<String> set = new java.util.HashSet<>();
        for (List<String> batch : batchedMarketIds) {
            if (batch != null) {
                set.addAll(batch);
            }
        }
        return set;
    }
}
