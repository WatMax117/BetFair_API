package com.netbet.streaming.sink;

import com.fasterxml.jackson.databind.JsonNode;
import com.netbet.streaming.cache.MarketCache;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import jakarta.annotation.PreDestroy;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Non-blocking PostgreSQL sink for high-frequency streaming data.
 * Dedicated worker thread + BlockingQueue; no DB writes on the streaming read loop.
 * Flush: every ~500 ms or ~200 records. Persists only the 5 allowed market types.
 */
@Component
@ConditionalOnProperty(name = "betfair.postgres-sink.enabled", havingValue = "true")
public class PostgresStreamEventSink implements StreamEventSink {

    private static final Logger log = LoggerFactory.getLogger(PostgresStreamEventSink.class);
    private static final Set<String> ALLOWED_MARKET_TYPES = Set.of(
            "MATCH_ODDS_FT", "OVER_UNDER_25_FT", "HALF_TIME_RESULT", "OVER_UNDER_05_HT", "NEXT_GOAL"
    );
    private static final Map<String, String> STREAM_TO_DB_MARKET_TYPE = Map.of(
            "MATCH_ODDS", "MATCH_ODDS_FT",
            "OVER_UNDER_25", "OVER_UNDER_25_FT",
            "HALF_TIME", "HALF_TIME_RESULT",
            "OVER_UNDER_05", "OVER_UNDER_05_HT",
            "OVER_UNDER_05_HT", "OVER_UNDER_05_HT",
            "NEXT_GOAL", "NEXT_GOAL"
    );
    private static final int MAX_LEVEL = 8;
    private static final String LADDER_SQL = "INSERT INTO ladder_levels (market_id, selection_id, side, level, price, size, publish_time, received_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (market_id, selection_id, side, level, publish_time) DO NOTHING";
    private static final String TRADED_SQL = "INSERT INTO traded_volume (market_id, selection_id, price, size_traded, publish_time, received_time) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (market_id, selection_id, price, publish_time) DO UPDATE SET size_traded = EXCLUDED.size_traded, received_time = EXCLUDED.received_time";
    private static final String LIFECYCLE_SQL = "INSERT INTO market_lifecycle_events (market_id, status, in_play, publish_time, received_time) VALUES (?, ?, ?, ?, ?)";
    private static final String LIQUIDITY_SQL = "INSERT INTO market_liquidity_history (market_id, publish_time, total_matched, max_runner_ltp) VALUES (?, ?, ?, ?) ON CONFLICT (market_id, publish_time) DO UPDATE SET total_matched = EXCLUDED.total_matched, max_runner_ltp = EXCLUDED.max_runner_ltp";
    private static final String UPDATE_MARKET_TOTAL_MATCHED = "UPDATE markets SET total_matched = GREATEST(COALESCE(total_matched, 0), ?) WHERE market_id = ?";

    private final BlockingQueue<QueueItem> queue = new LinkedBlockingQueue<>(50_000);
    private final MarketCache marketCache;
    private final JdbcTemplate jdbc;
    private final long flushIntervalMs;
    private final int batchSize;
    private final AtomicBoolean running = new AtomicBoolean(true);
    private final Thread worker;
    private final AtomicLong insertedRows = new AtomicLong(0);
    private final AtomicLong writeFailures = new AtomicLong(0);
    private final AtomicLong liquidityUpdateCount = new AtomicLong(0);
    private volatile long lastFlushDurationMs = 0;
    private volatile long lastErrorTimestamp = 0;

    public PostgresStreamEventSink(MarketCache marketCache,
                                   JdbcTemplate jdbc,
                                   @Value("${betfair.postgres-sink.flush-interval-ms:500}") long flushIntervalMs,
                                   @Value("${betfair.postgres-sink.batch-size:200}") int batchSize) {
        this.marketCache = marketCache;
        this.jdbc = jdbc;
        this.flushIntervalMs = flushIntervalMs > 0 ? flushIntervalMs : 500;
        this.batchSize = batchSize > 0 ? Math.min(2000, batchSize) : 200;
        this.worker = new Thread(this::runWorker, "postgres-sink-worker");
        this.worker.setDaemon(false);
        this.worker.start();
        log.info("PostgresStreamEventSink started (flushIntervalMs={}, batchSize={})", this.flushIntervalMs, this.batchSize);
    }

    /** Telemetry: total rows inserted (ladder + traded + lifecycle). */
    public long getInsertedRows() { return insertedRows.get(); }
    /** Telemetry: number of flush failures. */
    public long getWriteFailures() { return writeFailures.get(); }
    /** Telemetry: current queue size (on-demand). */
    public int getQueueSize() { return queue.size(); }
    /** Telemetry: last successful flush duration in ms. */
    public long getLastFlushDurationMs() { return lastFlushDurationMs; }
    /** Telemetry: epoch ms of last write failure (0 if none). */
    public long getLastErrorTimestamp() { return lastErrorTimestamp; }

    @Override
    public void onMarketChange(String marketId, String changeType, JsonNode payload, long receivedAt, long publishTime) {
        if (publishTime < 0) publishTime = receivedAt;
        if (!queue.offer(new SnapshotItem(marketId, publishTime, receivedAt))) {
            log.trace("Postgres sink queue full, drop snapshot marketId={}", marketId);
        }
    }

    @Override
    public void onMarketLifecycleEvent(String marketId, String status, Boolean inPlay,
                                       JsonNode marketDefinition, long receivedAt, long publishTime) {
        if (publishTime < 0) publishTime = receivedAt;
        if (!queue.offer(new LifecycleItem(marketId, status, inPlay, publishTime, receivedAt))) {
            log.trace("Postgres sink queue full, drop lifecycle marketId={}", marketId);
        }
    }

    private void runWorker() {
        List<QueueItem> batch = new ArrayList<>(batchSize);
        long lastFlush = System.currentTimeMillis();
        while (running.get()) {
            batch.clear();
            try {
                QueueItem first = queue.poll(flushIntervalMs, TimeUnit.MILLISECONDS);
                if (first != null) {
                    batch.add(first);
                    queue.drainTo(batch, batchSize - 1);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            long now = System.currentTimeMillis();
            if (batch.isEmpty()) continue;
            if (batch.size() >= batchSize || (now - lastFlush >= flushIntervalMs)) {
                flush(batch);
                lastFlush = now;
            }
        }
        if (!queue.isEmpty()) {
            queue.drainTo(batch);
            if (!batch.isEmpty()) flush(batch);
        }
    }

    private void flush(List<QueueItem> batch) {
        List<Object[]> ladderRows = new ArrayList<>();
        List<Object[]> tradedRows = new ArrayList<>();
        List<Object[]> lifecycleRows = new ArrayList<>();
        List<Object[]> liquidityRows = new ArrayList<>();
        for (QueueItem item : batch) {
            if (item instanceof SnapshotItem s) processSnapshot(s, ladderRows, tradedRows, liquidityRows);
            else if (item instanceof LifecycleItem l) addLifecycle(l, lifecycleRows);
        }
        long startMs = System.currentTimeMillis();
        try {
            if (!ladderRows.isEmpty()) insertedRows.addAndGet(countBatchResult(jdbc.batchUpdate(LADDER_SQL, ladderRows)));
            if (!tradedRows.isEmpty()) insertedRows.addAndGet(countBatchResult(jdbc.batchUpdate(TRADED_SQL, tradedRows)));
            if (!lifecycleRows.isEmpty()) insertedRows.addAndGet(countBatchResult(jdbc.batchUpdate(LIFECYCLE_SQL, lifecycleRows)));
            if (!liquidityRows.isEmpty()) {
                insertedRows.addAndGet(countBatchResult(jdbc.batchUpdate(LIQUIDITY_SQL, liquidityRows)));
                for (Object[] row : liquidityRows) {
                    jdbc.update(UPDATE_MARKET_TOTAL_MATCHED, row[2], row[0]);
                }
            }
            lastFlushDurationMs = System.currentTimeMillis() - startMs;
        } catch (Exception e) {
            writeFailures.incrementAndGet();
            lastErrorTimestamp = System.currentTimeMillis();
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            log.warn("Postgres sink flush failed: {} - {}", e.getMessage(), cause.getMessage());
        }
    }

    /** Count rows from batch update; treat SUCCESS_NO_INFO (-2) as 1 row. Log other negative values. */
    private int countBatchResult(int[] results) {
        if (results == null) return 0;
        int count = 0;
        for (int r : results) {
            if (r == java.sql.Statement.SUCCESS_NO_INFO || r < 0) {
                if (r != java.sql.Statement.SUCCESS_NO_INFO) {
                    log.warn("Unexpected batch result: {}", r);
                }
                count += 1;
            } else if (r > 0) {
                count += r;
            }
        }
        return count;
    }

    private void processSnapshot(SnapshotItem s, List<Object[]> ladderRows, List<Object[]> tradedRows, List<Object[]> liquidityRows) {
        MarketCache.CachedMarket market = marketCache.getMarket(s.marketId());
        if (market == null) return;
        String dbMarketType = resolveMarketType(market.getMarketDefinition());
        if (dbMarketType == null || !ALLOWED_MARKET_TYPES.contains(dbMarketType)) return;

        Instant publishTime = Instant.ofEpochMilli(s.publishTime());
        Instant receivedTime = Instant.ofEpochMilli(s.receivedAt());
        Timestamp publishTs = Timestamp.from(publishTime);
        Timestamp receivedTs = Timestamp.from(receivedTime);
        int levels = Math.min(MAX_LEVEL, MarketCache.DEFAULT_LADDER_LEVELS);

        // stream: value from marketDefinition.totalMatched (0 if missing/null)
        double stream = 0;
        JsonNode def = market.getMarketDefinition();
        if (def != null && !def.isMissingNode()) {
            stream = def.path("totalMatched").asDouble(0);
        }
        // fallback: sum(runner.totalMatched) from cache
        double fallback = 0;
        for (MarketCache.CachedRunner runner : market.getRunners().values()) {
            Double rv = runner.getTotalMatched();
            if (rv != null && rv > 0) fallback += rv;
        }
        // final: chosen value (stream when present, else fallback)
        double finalVolume = stream > 0 ? stream : fallback;

        long n = liquidityUpdateCount.incrementAndGet();
        if (n % 100 == 0) {
            log.info("Liquidity trace: Market ID | Stream: [{}] | Fallback: [{}] | Final: [{}]",
                    s.marketId(), stream, fallback, finalVolume);
        }

        double totalMatched = finalVolume;
        Double lastPriceTraded = null;
        for (MarketCache.CachedRunner runner : market.getRunners().values()) {
            Double ltp = runner.getLastTradedPrice();
            if (ltp != null) {
                if (lastPriceTraded == null || ltp > lastPriceTraded) lastPriceTraded = ltp;
            }
        }

        liquidityRows.add(new Object[]{
                s.marketId(),
                publishTs,
                totalMatched,
                lastPriceTraded != null ? lastPriceTraded : (Double) null
        });

        for (MarketCache.CachedRunner runner : market.getRunners().values()) {
            long selectionId = runner.getSelectionId();
            int level = 0;
            for (Map.Entry<Double, Double> e : runner.getBackLadder(levels)) {
                if (level >= MAX_LEVEL) break;
                ladderRows.add(new Object[]{s.marketId(), selectionId, "B", level, e.getKey(), e.getValue(), publishTs, receivedTs});
                level++;
            }
            level = 0;
            for (Map.Entry<Double, Double> e : runner.getLayLadder(levels)) {
                if (level >= MAX_LEVEL) break;
                ladderRows.add(new Object[]{s.marketId(), selectionId, "L", level, e.getKey(), e.getValue(), publishTs, receivedTs});
                level++;
            }
            for (Map.Entry<Double, Double> e : runner.getTradedVolume().entrySet()) {
                tradedRows.add(new Object[]{s.marketId(), selectionId, e.getKey(), e.getValue(), publishTs, receivedTs});
            }
        }
    }

    private String resolveMarketType(JsonNode marketDefinition) {
        if (marketDefinition == null || marketDefinition.isMissingNode()) return null;
        String raw = marketDefinition.path("marketType").asText(null);
        if (raw == null || raw.isBlank()) return null;
        return STREAM_TO_DB_MARKET_TYPE.getOrDefault(raw.trim().toUpperCase(), null);
    }

    private void addLifecycle(LifecycleItem l, List<Object[]> lifecycleRows) {
        Timestamp publishTs = Timestamp.from(Instant.ofEpochMilli(l.publishTime()));
        Timestamp receivedTs = Timestamp.from(Instant.ofEpochMilli(l.receivedAt()));
        lifecycleRows.add(new Object[]{l.marketId(), l.status(), l.inPlay(), publishTs, receivedTs});
    }

    @PreDestroy
    public void shutdown() {
        running.set(false);
        worker.interrupt();
    }

    private sealed interface QueueItem permits SnapshotItem, LifecycleItem {}

    private record SnapshotItem(String marketId, long publishTime, long receivedAt) implements QueueItem {}

    private record LifecycleItem(String marketId, String status, Boolean inPlay, long publishTime, long receivedAt) implements QueueItem {}
}
