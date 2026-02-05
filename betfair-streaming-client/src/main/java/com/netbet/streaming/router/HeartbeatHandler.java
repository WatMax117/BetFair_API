package com.netbet.streaming.router;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Handles heartbeat (ct=HEARTBEAT or empty mcm with ct=HEARTBEAT).
 * Heartbeats are diagnostic; status/error drive re-auth/reconnect.
 */
@Component
public class HeartbeatHandler {

    private static final Logger log = LoggerFactory.getLogger(HeartbeatHandler.class);

    public void handle(JsonNode root) {
        log.trace("Heartbeat received id={} status={}", root.path("id").asInt(-1), root.path("status").asText("null"));
    }
}
