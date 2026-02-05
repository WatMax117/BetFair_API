package com.netbet.streaming.router;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Handles op=connection. Log connectionId for support queries.
 */
@Component
public class ConnectionHandler {

    private static final Logger log = LoggerFactory.getLogger(ConnectionHandler.class);

    public void handle(JsonNode root) {
        String connectionId = root.path("connectionId").asText("");
        log.info("Stream connected. connectionId={} (supply on support queries)", connectionId);
    }
}
