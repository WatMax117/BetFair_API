package com.netbet.streaming.router;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Handles op=status. Status/error messages drive re-auth and reconnect logic.
 * Reference: All errors apart from SUBSCRIPTION_LIMIT_EXCEEDED close the connection.
 */
@Component
public class StatusHandler {

    private static final Logger log = LoggerFactory.getLogger(StatusHandler.class);

    public void handle(JsonNode root) {
        String statusCode = root.path("statusCode").asText("");
        String errorCode = root.path("errorCode").asText(null);
        String errorMessage = root.path("errorMessage").asText(null);
        boolean connectionClosed = root.path("connectionClosed").asBoolean(false);

        if ("SUCCESS".equals(statusCode)) {
            log.info("Stream request succeeded (id={})", root.path("id").asInt(-1));
            return;
        }
        if ("FAILURE".equals(statusCode)) {
            log.error("Stream error: errorCode={} errorMessage={} connectionClosed={} id={}",
                    errorCode, errorMessage, connectionClosed, root.path("id").asInt(-1));
            return;
        }
        log.debug("Status: statusCode={} id={}", statusCode, root.path("id").asInt(-1));
    }
}
