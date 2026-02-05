package com.netbet.streaming.metadata;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Cache for market metadata (teams, competition, kickoff). Split TTL: success 24h, missing 30min.
 * Supports "resolved/missing" sentinel to prevent infinite retry for closed markets.
 */
@Component
public class MetadataCache {

    private static final Logger log = LoggerFactory.getLogger(MetadataCache.class);
    private static final long DEFAULT_TTL_SUCCESS_SECONDS = 24 * 60 * 60;
    private static final long DEFAULT_TTL_MISSING_SECONDS = 30 * 60;

    private final long ttlSuccessSeconds;
    private final long ttlMissingSeconds;
    private final ConcurrentHashMap<String, Entry> cache = new ConcurrentHashMap<>();

    public MetadataCache(
            @Value("${betfair.metadata-cache.ttl-hours:24}") int ttlHours,
            @Value("${betfair.metadata-cache.missing-ttl-minutes:30}") int missingTtlMinutes) {
        this.ttlSuccessSeconds = ttlHours > 0 ? (long) ttlHours * 3600 : DEFAULT_TTL_SUCCESS_SECONDS;
        this.ttlMissingSeconds = missingTtlMinutes > 0 ? (long) missingTtlMinutes * 60 : DEFAULT_TTL_MISSING_SECONDS;
    }

    /**
     * Returns cached metadata if present and not expired. Empty if missing or expired.
     */
    public Optional<MarketMetadataRecord> get(String marketId) {
        Entry e = cache.get(marketId);
        if (e == null) return Optional.empty();
        if (e.isMissing) return Optional.empty();
        if (e.expiresAt != null && Instant.now().isAfter(e.expiresAt)) {
            cache.remove(marketId, e);
            return Optional.empty();
        }
        return Optional.ofNullable(e.record);
    }

    /**
     * True if we have already resolved this market (either have metadata or marked missing). Prevents re-submit.
     */
    public boolean isResolved(String marketId) {
        Entry e = cache.get(marketId);
        if (e == null) return false;
        if (e.expiresAt != null && Instant.now().isAfter(e.expiresAt)) {
            cache.remove(marketId, e);
            return false;
        }
        return true;
    }

    public void put(MarketMetadataRecord record) {
        if (record == null || record.marketId() == null) return;
        cache.put(record.marketId(), new Entry(record, false, Instant.now().plusSeconds(ttlSuccessSeconds)));
        log.debug("Metadata cached for marketId={} event={}", record.marketId(), record.eventName());
    }

    /**
     * Mark market as resolved but missing (empty catalogue result). Uses shorter TTL so market can be retried later if it appears.
     */
    public void putMissing(String marketId) {
        if (marketId == null || marketId.isBlank()) return;
        cache.put(marketId, new Entry(null, true, Instant.now().plusSeconds(ttlMissingSeconds)));
        log.debug("Market marked missing (no catalogue result): marketId={} ttl={}min", marketId, ttlMissingSeconds / 60);
    }

    private static final class Entry {
        final MarketMetadataRecord record;
        final boolean isMissing;
        final Instant expiresAt;

        Entry(MarketMetadataRecord record, boolean isMissing, Instant expiresAt) {
            this.record = record;
            this.isMissing = isMissing;
            this.expiresAt = expiresAt;
        }
    }
}
