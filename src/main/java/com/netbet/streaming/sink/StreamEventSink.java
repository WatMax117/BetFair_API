package com.netbet.streaming.sink;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Data sink for market updates. Decouples streaming logic from future persistence (e.g. PostgreSQL).
 * Reference: Spec "StreamEventSink Interface" for decoupled data flow.
 * Addendum: Lifecycle events (status, inPlay) passed through for goals, VAR, match endings.
 */
public interface StreamEventSink {

    /**
     * Called when a market change message (op=mcm) has been applied to the cache.
     * Implementations must not block; offload to another thread if needed.
     *
     * @param marketId   market id
     * @param changeType ct: SUB_IMAGE, RESUB_DELTA, HEARTBEAT, or null for delta
     * @param payload    raw mcm node for the market (or full mcm if multi-market)
     * @param receivedAt local server time when message was received (for latency metrics)
     * @param publishTime Betfair pt if present, else -1
     */
    void onMarketChange(String marketId, String changeType, JsonNode payload, long receivedAt, long publishTime);

    /**
     * Lifecycle events from marketDefinition: status (OPEN → SUSPENDED → CLOSED) and inPlay transitions.
     * Gold standard for goals, VAR interventions, and match endings in future DB analysis.
     * Implementations may track previous values to detect transitions.
     *
     * @param marketId        market id
     * @param status          market status (e.g. OPEN, SUSPENDED, CLOSED)
     * @param inPlay          true when market has turned in-play
     * @param marketDefinition full marketDefinition node (for suspendReason, marketTime, etc.)
     * @param receivedAt      local server time when message was received
     * @param publishTime     Betfair publish time (ms), or -1 if not present
     */
    default void onMarketLifecycleEvent(String marketId, String status, Boolean inPlay,
                                        JsonNode marketDefinition, long receivedAt, long publishTime) {
        // Optional: override to persist lifecycle events
    }
}
