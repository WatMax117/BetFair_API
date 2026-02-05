package com.netbet.streaming.controller;

import com.netbet.streaming.metadata.MarketMetadataHydrator;
import com.netbet.streaming.metadata.MarketMetadataRecord;
import com.netbet.streaming.metadata.MetadataCache;
import com.netbet.streaming.sink.PostgresStreamEventSink;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * REST endpoint for market metadata (teams, competition, kickoff). Resolved asynchronously by MarketMetadataHydrator.
 */
@RestController
@RequestMapping("/metadata")
public class MetadataController {

    private final MetadataCache metadataCache;
    private final Optional<MarketMetadataHydrator> hydrator;
    private final Optional<PostgresStreamEventSink> postgresSink;

    public MetadataController(MetadataCache metadataCache,
                              Optional<MarketMetadataHydrator> hydrator,
                              Optional<PostgresStreamEventSink> postgresSink) {
        this.metadataCache = metadataCache;
        this.hydrator = hydrator != null ? hydrator : Optional.empty();
        this.postgresSink = postgresSink != null ? postgresSink : Optional.empty();
    }

    @GetMapping("/{marketId}")
    public ResponseEntity<Map<String, Object>> get(@PathVariable String marketId) {
        Optional<MarketMetadataRecord> opt = metadataCache.get(marketId);
        if (opt.isEmpty()) {
            return ResponseEntity.notFound().build();
        }
        MarketMetadataRecord m = opt.get();
        Map<String, Object> result = new HashMap<>();
        result.put("marketId", m.marketId());
        result.put("eventId", m.eventId());
        result.put("eventName", m.eventName());
        result.put("competitionId", m.competitionId());
        result.put("competitionName", m.competitionName());
        result.put("marketStartTime", m.marketStartTime() != null ? m.marketStartTime().toString() : null);
        result.put("homeTeam", m.homeTeam());
        result.put("awayTeam", m.awayTeam());
        result.put("runners", m.runners().stream()
                .map(r -> Map.<String, Object>of("selectionId", r.selectionId(), "runnerName", r.runnerName()))
                .toList());
        return ResponseEntity.ok(result);
    }

    /**
     * Hydrator telemetry: total_calls, transient_errors, resolved_metadata, resolved_missing, requeued_ids_total, pending_queue_size (on-demand queue.size()).
     */
    @GetMapping("/telemetry")
    public ResponseEntity<Map<String, Object>> telemetry() {
        if (hydrator.isEmpty()) {
            return ResponseEntity.ok(Map.of());
        }
        MarketMetadataHydrator h = hydrator.get();
        Map<String, Object> result = new HashMap<>();
        result.put("total_calls", h.getTotalCalls());
        result.put("transient_errors", h.getTransientErrors());
        result.put("resolved_metadata", h.getResolvedMetadata());
        result.put("resolved_missing", h.getResolvedMissing());
        result.put("requeued_ids_total", h.getRequeuedIdsTotal());
        result.put("pending_queue_size", h.getPendingQueueSize());
        postgresSink.ifPresent(sink -> {
            result.put("postgres_sink_inserted_rows", sink.getInsertedRows());
            result.put("postgres_sink_write_failures", sink.getWriteFailures());
            result.put("postgres_sink_queue_size", sink.getQueueSize());
            result.put("postgres_sink_last_flush_duration_ms", sink.getLastFlushDurationMs());
            result.put("postgres_sink_last_error_timestamp", sink.getLastErrorTimestamp());
        });
        return ResponseEntity.ok(result);
    }
}
