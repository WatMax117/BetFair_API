package com.netbet.streaming.router;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Centralized routing for stream messages by op: connection, status, heartbeat, mcm (marketChange).
 * Single-threaded read loop passes parsed JSON here; no I/O or DB in the loop.
 */
@Component
public class MessageRouter {

    private static final Logger log = LoggerFactory.getLogger(MessageRouter.class);
    private final ObjectMapper objectMapper;
    private final ConnectionHandler connectionHandler;
    private final StatusHandler statusHandler;
    private final HeartbeatHandler heartbeatHandler;
    private final MarketChangeHandler marketChangeHandler;

    public MessageRouter(ObjectMapper objectMapper,
                         ConnectionHandler connectionHandler,
                         StatusHandler statusHandler,
                         HeartbeatHandler heartbeatHandler,
                         MarketChangeHandler marketChangeHandler) {
        this.objectMapper = objectMapper;
        this.connectionHandler = connectionHandler;
        this.statusHandler = statusHandler;
        this.heartbeatHandler = heartbeatHandler;
        this.marketChangeHandler = marketChangeHandler;
    }

    /**
     * Route one CRLF-delimited JSON message. No blocking I/O or DB calls.
     */
    public void route(String jsonLine, long receivedTimeMs) {
        if (jsonLine == null || jsonLine.isBlank()) {
            return;
        }
        try {
            JsonNode root = objectMapper.readTree(jsonLine);
            String op = root.path("op").asText("");

            switch (op) {
                case "connection" -> connectionHandler.handle(root);
                case "status" -> statusHandler.handle(root);
                case "mcm" -> marketChangeHandler.handle(root, receivedTimeMs);
                default -> {
                    if ("HEARTBEAT".equals(root.path("ct").asText(null))) {
                        heartbeatHandler.handle(root);
                    } else {
                        log.trace("Unhandled op: {}", op);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("Failed to parse or route message: {}", e.getMessage());
        }
    }
}
