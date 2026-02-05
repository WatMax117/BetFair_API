package com.netbet.streaming.cache;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PreDestroy;
import java.io.File;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * State machine for Betfair Stream API: Initial Image + Deltas.
 * - Atomic updates at market level (no partial state reads).
 * - Sequence: SUB_IMAGE / img=true replaces state; deltas applied in order (clk stored for resubscribe).
 * - Fresh image policy: call clearAll() on reconnect before re-subscribing.
 * Reference: Betfair Exchange Stream API - Building a price cache, Re-connection / Re-subscription.
 */
@Component
public class MarketCache {

    private static final Logger log = LoggerFactory.getLogger(MarketCache.class);
    private static final String BACK = "BACK";
    private static final String LAY = "LAY";
    /** Default order book depth (Back/Lay) for soccer markets. */
    public static final int DEFAULT_LADDER_LEVELS = 8;

    private final Map<String, CachedMarket> markets = new ConcurrentHashMap<>();
    private volatile CsvLoggingHandler csvHandler;
    /** Last clk applied (opaque token for resubscribe; diagnostic). */
    private volatile String lastClk;

    public MarketCache(
            @Value("${betfair.csv-logging.enabled:false}") boolean csvEnabled,
            @Value("${betfair.csv-logging.output-dir:./logs}") String outputDir) {
        if (csvEnabled) {
            try {
                File dir = new File(outputDir);
                dir.mkdirs();
                this.csvHandler = new CsvLoggingHandler(dir);
                log.info("CSV logging enabled: {}", dir.getAbsolutePath());
            } catch (IOException e) {
                log.warn("Failed to init CSV logging: {}", e.getMessage());
            }
        }
    }

    @PreDestroy
    public void closeCsvWriters() {
        if (csvHandler != null) {
            csvHandler.close();
        }
    }

    public void closeCsvWritersIfOpen() {
        if (csvHandler != null) {
            csvHandler.close();
            csvHandler = null;
        }
    }

    /**
     * Clear all cached markets. Call on reconnection before requesting a new initial image (fresh image policy).
     */
    public void clearAll() {
        markets.clear();
        lastClk = null;
        log.info("Market cache cleared (fresh image policy)");
    }

    /**
     * Apply a market change message (op: mcm) from the stream. Updates are atomic at market level.
     */
    public void applyMarketChange(JsonNode mcm) {
        JsonNode mcArray = mcm.path("mc");
        if (mcArray == null || !mcArray.isArray()) return;

        String ct = mcm.path("ct").asText(null);
        if ("HEARTBEAT".equals(ct)) return;

        String clk = mcm.path("clk").asText(null);
        if (clk != null && !clk.isBlank()) {
            this.lastClk = clk;
        }

        for (JsonNode mc : mcArray) {
            String marketId = mc.path("id").asText(null);
            if (marketId == null) continue;

            boolean isFullImage = Boolean.TRUE.equals(mc.path("img").asBoolean(false))
                    || "SUB_IMAGE".equals(ct) || "RESUB_DELTA".equals(ct);

            CachedMarket market = markets.computeIfAbsent(marketId, CachedMarket::new);
            market.applyChange(mc, isFullImage, csvHandler);
            log.debug("Market {} updated, isFullImage={}", marketId, isFullImage);
        }
    }

    public String getLastClk() {
        return lastClk;
    }

    public CachedMarket getMarket(String marketId) {
        return markets.get(marketId);
    }

    public Map<String, CachedMarket> getAllMarkets() {
        return Collections.unmodifiableMap(markets);
    }

    /**
     * Cached market with reconstructed price ladders per runner.
     */
    public static class CachedMarket {
        private final String marketId;
        private JsonNode marketDefinition;
        private final Map<Long, CachedRunner> runners = new ConcurrentHashMap<>();

        public CachedMarket(String marketId) {
            this.marketId = marketId;
        }

        void clear() {
            runners.clear();
        }

        void setMarketDefinition(JsonNode md) {
            this.marketDefinition = md;
        }

        /** Atomic update at market level: definition + all runner changes under one lock. */
        synchronized void applyChange(JsonNode mc, boolean isFullImage, CsvLoggingHandler csv) {
            if (isFullImage) {
                runners.clear();
            }
            JsonNode md = mc.path("marketDefinition");
            if (md != null && !md.isMissingNode()) {
                this.marketDefinition = md;
            }
            JsonNode rc = mc.path("rc");
            if (rc != null && rc.isArray()) {
                for (JsonNode runnerChange : rc) {
                    applyRunnerChange(runnerChange, isFullImage, csv);
                }
            }
        }

        void applyRunnerChange(JsonNode rc, boolean isFullImage, CsvLoggingHandler csv) {
            long selectionId = rc.path("id").asLong(-1);
            if (selectionId < 0) return;

            CachedRunner runner = runners.computeIfAbsent(selectionId, CachedRunner::new);
            if (isFullImage) {
                runner.clear();
            }
            runner.applyDelta(rc, marketId, csv);
        }

        public String getMarketId() {
            return marketId;
        }

        public JsonNode getMarketDefinition() {
            return marketDefinition;
        }

        public Map<Long, CachedRunner> getRunners() {
            return Collections.unmodifiableMap(runners);
        }
    }

    /**
     * Cached runner with full price ladder (backs, lays, traded).
     */
    public static class CachedRunner {
        private final long selectionId;
        private final TreeMap<Double, Double> backLadder = new TreeMap<>(Comparator.reverseOrder());
        private final TreeMap<Double, Double> layLadder = new TreeMap<>();
        private final TreeMap<Double, Double> tradedVolume = new TreeMap<>(Comparator.reverseOrder());
        private Double lastTradedPrice;
        private Double totalMatched;

        public CachedRunner(long selectionId) {
            this.selectionId = selectionId;
        }

        void clear() {
            backLadder.clear();
            layLadder.clear();
            tradedVolume.clear();
            lastTradedPrice = null;
            totalMatched = null;
        }

        void applyDelta(JsonNode rc, String marketId, CsvLoggingHandler csv) {
            long ts = System.currentTimeMillis();

            applyLevelPriceVol(rc.path("bdatb"), backLadder, marketId, BACK, csv, ts);
            applyLevelPriceVol(rc.path("bdatl"), layLadder, marketId, LAY, csv, ts);
            if (!rc.has("bdatb")) applyLevelPriceVol(rc.path("batb"), backLadder, marketId, BACK, csv, ts);
            if (!rc.has("bdatl")) applyLevelPriceVol(rc.path("batl"), layLadder, marketId, LAY, csv, ts);

            applyPriceVol(rc.path("atb"), backLadder, marketId, BACK, csv, ts);
            applyPriceVol(rc.path("atl"), layLadder, marketId, LAY, csv, ts);

            // TRD_INCOMING debug (comment out to reduce log noise; re-enable for payload inspection)
            // if (rc.has("trd")) {
            //     log.info("TRD_INCOMING: Market {} | Runner {} | Payload: {}", marketId, selectionId, rc.path("trd").toString());
            // }
            applyTraded(rc.path("trd"), marketId, csv, ts);

            if (rc.has("ltp")) {
                lastTradedPrice = rc.path("ltp").asDouble();
            }
            if (rc.has("tv")) {
                totalMatched = rc.path("tv").asDouble();
            } else if (!tradedVolume.isEmpty()) {
                // Fallback: Betfair may not send "tv"; derive from trd (traded) map sum
                totalMatched = tradedVolume.values().stream().mapToDouble(Double::doubleValue).sum();
            }
        }

        private void applyLevelPriceVol(JsonNode arr, Map<Double, Double> ladder, String marketId, String side, CsvLoggingHandler csv, long ts) {
            if (arr == null || !arr.isArray()) return;
            for (JsonNode tuple : arr) {
                if (!tuple.isArray() || tuple.size() < 3) continue;
                int level = (int) tuple.get(0).asDouble();
                double price = tuple.get(1).asDouble();
                double vol = tuple.get(2).asDouble();
                Double oldSize = ladder.get(price);
                if (vol <= 0) {
                    ladder.remove(price);
                } else {
                    ladder.put(price, vol);
                    if (csv != null) {
                        csv.logPrice(ts, marketId, selectionId, side, price, vol, level);
                        csv.checkAndLogLiquidityEvent(marketId, selectionId, side, price, level, oldSize != null ? oldSize : 0, vol);
                    }
                }
            }
        }

        private void applyPriceVol(JsonNode arr, Map<Double, Double> ladder, String marketId, String side, CsvLoggingHandler csv, long ts) {
            if (arr == null || !arr.isArray()) return;
            int level = 0;
            for (JsonNode tuple : arr) {
                if (!tuple.isArray() || tuple.size() < 2) continue;
                double price = tuple.get(0).asDouble();
                double vol = tuple.get(1).asDouble();
                Double oldSize = ladder.get(price);
                if (vol <= 0) {
                    ladder.remove(price);
                } else {
                    ladder.put(price, vol);
                    if (csv != null) {
                        csv.logPrice(ts, marketId, selectionId, side, price, vol, level);
                        csv.checkAndLogLiquidityEvent(marketId, selectionId, side, price, level, oldSize != null ? oldSize : 0, vol);
                    }
                }
                level++;
            }
        }

        private void applyTraded(JsonNode arr, String marketId, CsvLoggingHandler csv, long ts) {
            if (arr == null || !arr.isArray()) return;
            for (JsonNode tuple : arr) {
                if (!tuple.isArray() || tuple.size() < 2) continue;
                double price = tuple.get(0).asDouble();
                double vol = tuple.get(1).asDouble();
                if (vol <= 0) {
                    tradedVolume.remove(price);
                } else {
                    tradedVolume.merge(price, vol, Double::sum);
                    if (csv != null) {
                        csv.logVolume(ts, marketId, selectionId, price, vol);
                    }
                }
            }
        }

        public long getSelectionId() {
            return selectionId;
        }

        /** Top N levels for Back (default 8 per spec). */
        public List<Map.Entry<Double, Double>> getBackLadder(int levels) {
            return getTopN(backLadder.entrySet(), levels <= 0 ? DEFAULT_LADDER_LEVELS : levels);
        }

        /** Top N levels for Lay (default 8 per spec). */
        public List<Map.Entry<Double, Double>> getLayLadder(int levels) {
            return getTopN(layLadder.entrySet(), levels <= 0 ? DEFAULT_LADDER_LEVELS : levels);
        }

        public Map<Double, Double> getTradedVolume() {
            return Collections.unmodifiableMap(tradedVolume);
        }

        public Double getLastTradedPrice() {
            return lastTradedPrice;
        }

        public Double getTotalMatched() {
            return totalMatched;
        }

        private static List<Map.Entry<Double, Double>> getTopN(Set<Map.Entry<Double, Double>> entries, int n) {
            return entries.stream().limit(n).toList();
        }
    }
}
