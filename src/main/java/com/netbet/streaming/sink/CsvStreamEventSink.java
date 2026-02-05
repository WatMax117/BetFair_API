package com.netbet.streaming.sink;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Optional StreamEventSink when csv-logging is enabled. Logs latency and lifecycle events (status, inPlay).
 */
@Component
@ConditionalOnProperty(name = "betfair.csv-logging.enabled", havingValue = "true")
public class CsvStreamEventSink implements StreamEventSink {

    private static final Logger log = LoggerFactory.getLogger(CsvStreamEventSink.class);

    @Override
    public void onMarketChange(String marketId, String changeType, JsonNode payload, long receivedAt, long publishTime) {
        if (publishTime >= 0) {
            long lagMs = receivedAt - publishTime;
            log.trace("Latency marketId={} lagMs={}", marketId, lagMs);
        }
    }

    @Override
    public void onMarketLifecycleEvent(String marketId, String status, Boolean inPlay,
                                       JsonNode marketDefinition, long receivedAt, long publishTime) {
        if (status != null || inPlay != null) {
            log.info("Lifecycle marketId={} status={} inPlay={} receivedAt={}", marketId, status, inPlay, receivedAt);
        }
    }
}
