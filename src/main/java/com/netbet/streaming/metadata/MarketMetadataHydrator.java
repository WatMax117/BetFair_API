package com.netbet.streaming.metadata;

import com.netbet.streaming.session.SessionProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PreDestroy;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Non-blocking metadata enrichment: queues marketId requests, batches (500ms or 25 items),
 * calls listMarketCatalogue via SessionProvider token, updates MetadataCache.
 * Transient errors: 2-step adaptive backoff (first 5s, consecutive 10s); reset on success.
 * Telemetry: total_calls, transient_errors, resolved_metadata, resolved_missing, requeued_ids_total, pending_queue_size (on-demand queue.size()).
 * Burst alert: immediate WARN if transient_errors increases by 5 since last telemetry log.
 */
@Component
public class MarketMetadataHydrator {

    private static final Logger log = LoggerFactory.getLogger(MarketMetadataHydrator.class);
    private static final int DEFAULT_BATCH_INTERVAL_MS = 500;
    private static final int DEFAULT_BATCH_SIZE = 25;
    private static final long DEFAULT_MIN_INTERVAL_MS = 200;
    private static final long DEFAULT_FIRST_TRANSIENT_BACKOFF_MS = 5000;
    private static final long DEFAULT_CONSECUTIVE_TRANSIENT_BACKOFF_MS = 10000;
    private static final int TELEMETRY_LOG_EVERY_BATCHES = 20;
    private static final int BURST_ALERT_THRESHOLD = 5;

    private final LinkedBlockingQueue<String> queue = new LinkedBlockingQueue<>();
    private final Set<String> pendingIds = ConcurrentHashMap.newKeySet();
    private final MetadataCache metadataCache;
    private final BettingApiClient bettingApiClient;
    private final SessionProvider sessionProvider;
    private final Optional<PostgresMetadataStore> metadataStore;
    private final long batchIntervalMs;
    private final int batchSize;
    private final long minIntervalMs;
    private final long apiDelayMs;
    private final long firstTransientBackoffMs;
    private final long consecutiveTransientBackoffMs;
    private final AtomicBoolean running = new AtomicBoolean(true);
    private final Thread worker;

    private final AtomicLong totalCalls = new AtomicLong(0);
    private final AtomicLong transientErrors = new AtomicLong(0);
    private final AtomicLong resolvedMetadata = new AtomicLong(0);
    private final AtomicLong resolvedMissing = new AtomicLong(0);
    private final AtomicLong requeuedIdsTotal = new AtomicLong(0);
    private int batchCountSinceLog = 0;
    private long lastLoggedTransientErrors = 0;
    private int consecutiveTransientCount = 0;

    public MarketMetadataHydrator(MetadataCache metadataCache,
                                  BettingApiClient bettingApiClient,
                                  SessionProvider sessionProvider,
                                  Optional<PostgresMetadataStore> metadataStore,
                                  @Value("${betfair.metadata-hydrator.batch-interval-ms:500}") long batchIntervalMs,
                                  @Value("${betfair.metadata-hydrator.batch-size:25}") int batchSize,
                                  @Value("${betfair.metadata-hydrator.min-interval-ms:200}") long minIntervalMs,
                                  @Value("${betfair.metadata-hydrator.api-delay-ms:1000}") long apiDelayMs,
                                  @Value("${betfair.metadata-hydrator.first-transient-backoff-ms:5000}") long firstTransientBackoffMs,
                                  @Value("${betfair.metadata-hydrator.consecutive-transient-backoff-ms:10000}") long consecutiveTransientBackoffMs) {
        this.metadataCache = metadataCache;
        this.bettingApiClient = bettingApiClient;
        this.sessionProvider = sessionProvider;
        this.metadataStore = metadataStore != null ? metadataStore : Optional.empty();
        this.batchIntervalMs = batchIntervalMs > 0 ? batchIntervalMs : DEFAULT_BATCH_INTERVAL_MS;
        this.batchSize = batchSize > 0 ? Math.min(1000, batchSize) : DEFAULT_BATCH_SIZE;
        this.minIntervalMs = minIntervalMs > 0 ? minIntervalMs : DEFAULT_MIN_INTERVAL_MS;
        this.apiDelayMs = apiDelayMs > 0 ? apiDelayMs : 1000L;
        this.firstTransientBackoffMs = firstTransientBackoffMs > 0 ? firstTransientBackoffMs : DEFAULT_FIRST_TRANSIENT_BACKOFF_MS;
        this.consecutiveTransientBackoffMs = consecutiveTransientBackoffMs > 0 ? consecutiveTransientBackoffMs : DEFAULT_CONSECUTIVE_TRANSIENT_BACKOFF_MS;
        this.worker = new Thread(this::runWorker, "metadata-hydrator");
        this.worker.setDaemon(true);
        this.worker.start();
        log.info("MarketMetadataHydrator started (batchIntervalMs={}, batchSize={}, minIntervalMs={}, apiDelayMs={}, firstTransientBackoffMs={}, consecutiveTransientBackoffMs={})",
                this.batchIntervalMs, this.batchSize, this.minIntervalMs, this.apiDelayMs, this.firstTransientBackoffMs, this.consecutiveTransientBackoffMs);
    }

    /** Telemetry: total listMarketCatalogue API calls. */
    public long getTotalCalls() { return totalCalls.get(); }
    /** Telemetry: calls that returned transient error (429/5xx). */
    public long getTransientErrors() { return transientErrors.get(); }
    /** Telemetry: markets successfully resolved with metadata. */
    public long getResolvedMetadata() { return resolvedMetadata.get(); }
    /** Telemetry: markets resolved as missing (not in catalogue). */
    public long getResolvedMissing() { return resolvedMissing.get(); }
    /** Telemetry: total market IDs re-queued due to transient errors (API pressure indicator). */
    public long getRequeuedIdsTotal() { return requeuedIdsTotal.get(); }
    /** Telemetry: on-demand queue size via queue.size() for 100% accuracy (not a manual counter). */
    public int getPendingQueueSize() { return queue.size(); }

    /**
     * Submit a marketId for metadata resolution. Non-blocking; does not wait for response.
     * Skips if already resolved or already pending.
     */
    public void submit(String marketId) {
        if (marketId == null || marketId.isBlank()) return;
        if (metadataCache.isResolved(marketId)) return;
        if (!pendingIds.add(marketId)) return;
        queue.offer(marketId);
    }

    private void runWorker() {
        List<String> batch = new ArrayList<>(batchSize);
        while (running.get()) {
            batch.clear();
            try {
                String first = queue.poll(batchIntervalMs, TimeUnit.MILLISECONDS);
                if (first != null) {
                    batch.add(first);
                    queue.drainTo(batch, batchSize - 1);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            if (batch.isEmpty()) continue;

            String token;
            try {
                token = sessionProvider.getValidSession();
            } catch (SessionProvider.SessionException e) {
                log.warn("Hydrator: session unavailable, re-queuing {} ids for next cycle", batch.size());
                batch.forEach(id -> { pendingIds.remove(id); queue.offer(id); });
                continue;
            }

            totalCalls.incrementAndGet();
            CatalogueFetchResult result = bettingApiClient.listMarketCatalogue(token, batch);

            if (result.isTransientError()) {
                transientErrors.incrementAndGet();
                consecutiveTransientCount++;
                int requeued = batch.size();
                requeuedIdsTotal.addAndGet(requeued);
                for (String id : batch) {
                    pendingIds.remove(id);
                    queue.offer(id);
                }
                long backoffMs = consecutiveTransientCount == 1 ? firstTransientBackoffMs : consecutiveTransientBackoffMs;
                log.debug("Hydrator: transient error, re-queued {} ids (backoff {}ms, consecutive={})", requeued, backoffMs, consecutiveTransientCount);
                if (transientErrors.get() - lastLoggedTransientErrors >= BURST_ALERT_THRESHOLD) {
                    log.warn("[ALERT] Rapid transient error increase detected! Metrics: total_calls={} transient_errors={} resolved_metadata={} resolved_missing={} requeued_ids_total={} pending_queue_size={}",
                            totalCalls.get(), transientErrors.get(), resolvedMetadata.get(), resolvedMissing.get(), requeuedIdsTotal.get(), getPendingQueueSize());
                    lastLoggedTransientErrors = transientErrors.get();
                }
                sleep(Math.max(backoffMs, apiDelayMs));
                if (interrupted()) break;
            } else {
                consecutiveTransientCount = 0;
                int putCount = 0;
                int missingCount = 0;
                for (MarketMetadataRecord r : result.records()) {
                    if (r != null && r.marketId() != null) {
                        metadataCache.put(r);
                        metadataStore.ifPresent(store -> store.persist(r));
                        pendingIds.remove(r.marketId());
                        putCount++;
                    }
                }
                for (String id : batch) {
                    if (!pendingIds.contains(id)) continue;
                    metadataCache.putMissing(id);
                    pendingIds.remove(id);
                    missingCount++;
                }
                resolvedMetadata.addAndGet(putCount);
                resolvedMissing.addAndGet(missingCount);
                sleep(Math.max(minIntervalMs, apiDelayMs));
                if (interrupted()) break;
            }

            if (++batchCountSinceLog >= TELEMETRY_LOG_EVERY_BATCHES) {
                batchCountSinceLog = 0;
                lastLoggedTransientErrors = transientErrors.get();
                log.info("Metadata hydrator telemetry: total_calls={} transient_errors={} resolved_metadata={} resolved_missing={} requeued_ids_total={} pending_queue_size={}",
                        totalCalls.get(), transientErrors.get(), resolvedMetadata.get(), resolvedMissing.get(), requeuedIdsTotal.get(), getPendingQueueSize());
            }
        }
    }

    private void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private boolean interrupted() {
        return Thread.currentThread().isInterrupted();
    }

    @PreDestroy
    public void shutdown() {
        running.set(false);
        worker.interrupt();
    }
}
