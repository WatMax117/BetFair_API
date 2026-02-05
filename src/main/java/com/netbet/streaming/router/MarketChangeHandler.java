package com.netbet.streaming.router;

import com.fasterxml.jackson.databind.JsonNode;
import com.netbet.streaming.cache.MarketCache;
import com.netbet.streaming.metadata.MarketMetadataHydrator;
import com.netbet.streaming.metadata.MetadataCache;
import com.netbet.streaming.sink.StreamEventSink;
import com.netbet.streaming.subscription.SubscriptionManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;

/**
 * Handles op=mcm (MarketChangeMessage). Updates cache and subscription clocks; graduated latency alerts;
 * notifies sink (market changes + lifecycle events: status, inPlay).
 * Non-blocking metadata: if metadata not resolved for marketId, submits to MarketMetadataHydrator (no wait).
 */
@Component
public class MarketChangeHandler {

    private static final Logger log = LoggerFactory.getLogger(MarketChangeHandler.class);

    /** Graduated latency: INFO > 200ms, WARN > 500ms, ERROR > 2000ms (critical for high-frequency). */
    private static final long LATENCY_INFO_MS = 200;
    private static final long LATENCY_WARN_MS = 500;
    private static final long LATENCY_ERROR_MS = 2000;

    private final MarketCache marketCache;
    private final SubscriptionManager subscriptionManager;
    private final List<StreamEventSink> sinks;
    private final Optional<MarketMetadataHydrator> metadataHydrator;
    private final Optional<MetadataCache> metadataCache;

    @Autowired(required = false)
    public MarketChangeHandler(MarketCache marketCache,
                               SubscriptionManager subscriptionManager,
                               List<StreamEventSink> sinks,
                               Optional<MarketMetadataHydrator> metadataHydrator,
                               Optional<MetadataCache> metadataCache) {
        this.marketCache = marketCache;
        this.subscriptionManager = subscriptionManager;
        this.sinks = sinks != null ? sinks : List.of();
        this.metadataHydrator = metadataHydrator != null ? metadataHydrator : Optional.empty();
        this.metadataCache = metadataCache != null ? metadataCache : Optional.empty();
    }

    public void handle(JsonNode root, long receivedTimeMs) {
        String ct = root.path("ct").asText(null);
        if ("HEARTBEAT".equals(ct)) {
            subscriptionManager.updateClocks(root.path("initialClk").asText(null), root.path("clk").asText(null));
            return;
        }

        long publishTime = root.has("pt") ? root.path("pt").asLong(-1) : -1;
        if (publishTime >= 0) {
            long lagMs = receivedTimeMs - publishTime;
            logLatency(lagMs, publishTime, receivedTimeMs);
        }

        subscriptionManager.updateClocks(root.path("initialClk").asText(null), root.path("clk").asText(null));
        marketCache.applyMarketChange(root);

        JsonNode mcArray = root.path("mc");
        if (mcArray == null || !mcArray.isArray()) return;

        for (JsonNode mc : mcArray) {
            String marketId = mc.path("id").asText(null);
            if (marketId == null) continue;
            if (metadataHydrator.isPresent() && metadataCache.isPresent()) {
                if (!metadataCache.get().isResolved(marketId)) {
                    metadataHydrator.get().submit(marketId);
                } else {
                    metadataCache.get().get(marketId)
                            .filter(r -> r.eventName() == null || r.eventName().isBlank())
                            .ifPresent(__ -> metadataHydrator.get().submit(marketId));
                }
            }
            for (StreamEventSink s : sinks) s.onMarketChange(marketId, ct, mc, receivedTimeMs, publishTime);

            JsonNode md = mc.path("marketDefinition");
            if (md != null && !md.isMissingNode()) {
                String status = md.path("status").asText(null);
                Boolean inPlay = md.has("inPlay") && !md.path("inPlay").isNull() ? md.path("inPlay").asBoolean() : null;
                if (status != null || inPlay != null) {
                    for (StreamEventSink s : sinks) s.onMarketLifecycleEvent(marketId, status, inPlay, md, receivedTimeMs, publishTime);
                }
            }
        }
    }

    private void logLatency(long lagMs, long publishTime, long receivedTimeMs) {
        if (lagMs > LATENCY_ERROR_MS) {
            log.error("Stream latency CRITICAL (data stale for high-frequency): lagMs={} publishTime={} receivedTime={}",
                    lagMs, publishTime, receivedTimeMs);
        } else if (lagMs > LATENCY_WARN_MS) {
            log.warn("Stream latency (potential bottleneck/congestion): lagMs={} publishTime={} receivedTime={}",
                    lagMs, publishTime, receivedTimeMs);
        } else if (lagMs > LATENCY_INFO_MS) {
            log.info("Stream latency (normal jitter): lagMs={} publishTime={} receivedTime={}", lagMs, publishTime, receivedTimeMs);
        } else {
            log.trace("Stream latency: lagMs={}", lagMs);
        }
    }
}
