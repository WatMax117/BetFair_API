package com.netbet.streaming.stream;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.List;

/**
 * Builds Betfair Stream API request messages.
 */
public final class StreamMessages {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private StreamMessages() {}

    public static String authentication(int id, String sessionToken, String appKey) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("op", "authentication");
        root.put("id", id);
        root.put("session", sessionToken);
        root.put("appKey", appKey);
        return root.toString();
    }

    /**
     * Market subscription: MATCH_ODDS, CORRECT_SCORE, TOTAL_GOALS, HALF_TIME,
     * HALFTIME_SCORE, OVER_UNDER_05_HT, OVER_UNDER_15_HT, NEXT_GOAL.
     * ladderLevels: 10, fields: EX_ALL_OFFERS, EX_TRADED_VOL, EX_TRADED.
     *
     * @param marketIds optional; if non-empty, subscribe to these specific market IDs
     */
    public static String marketSubscription(int id, int heartbeatMs, int conflateMs, List<String> marketIds) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("op", "marketSubscription");
        root.put("id", id);
        root.put("heartbeatMs", heartbeatMs);
        root.put("conflateMs", conflateMs);

        ObjectNode marketFilter = MAPPER.createObjectNode();
        if (marketIds != null && !marketIds.isEmpty()) {
            ArrayNode ids = MAPPER.createArrayNode();
            marketIds.forEach(ids::add);
            marketFilter.set("marketIds", ids);
        } else {
            ArrayNode eventTypeIds = MAPPER.createArrayNode();
            eventTypeIds.add("1");
            marketFilter.set("eventTypeIds", eventTypeIds);
            ArrayNode marketTypeCodes = MAPPER.createArrayNode();
            marketTypeCodes.add("MATCH_ODDS").add("CORRECT_SCORE").add("TOTAL_GOALS").add("HALF_TIME")
                    .add("HALFTIME_SCORE").add("OVER_UNDER_05_HT").add("OVER_UNDER_15_HT").add("NEXT_GOAL");
            marketFilter.set("marketTypeCodes", marketTypeCodes);
        }
        root.set("marketFilter", marketFilter);

        ObjectNode marketDataFilter = MAPPER.createObjectNode();
        marketDataFilter.put("ladderLevels", 10);
        ArrayNode fields = MAPPER.createArrayNode();
        fields.add("EX_ALL_OFFERS").add("EX_TRADED_VOL").add("EX_TRADED");
        marketDataFilter.set("fields", fields);
        root.set("marketDataFilter", marketDataFilter);

        return root.toString();
    }
}
