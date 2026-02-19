package com.netbet.streaming.metadata;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;

/**
 * Calls Betfair Exchange Betting API listMarketCatalogue.
 * Returns CatalogueFetchResult with records + isTransientError (429, 5xx, timeouts, JSON-RPC TOO_MANY_REQUESTS/SERVICE_BUSY).
 */
@Component
public class BettingApiClient {

    private static final Logger log = LoggerFactory.getLogger(BettingApiClient.class);
    private static final String METHOD = "SportsAPING/v1.0/listMarketCatalogue";

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final String apiUrl;
    private final String appKey;

    public BettingApiClient(RestClient.Builder restClientBuilder,
                            ObjectMapper objectMapper,
                            @Value("${betfair.betting-api-url:https://api.betfair.com/exchange/betting/json-rpc/v1}") String apiUrl,
                            @Value("${betfair.app-key}") String appKey) {
        this.restClient = restClientBuilder.build();
        this.objectMapper = objectMapper;
        this.apiUrl = apiUrl;
        this.appKey = appKey;
    }

    /**
     * Fetch metadata for the given market IDs.
     * isTransientError = true if 429, 5xx, SocketTimeoutException, ConnectException, or JSON-RPC TOO_MANY_REQUESTS/SERVICE_BUSY.
     */
    public CatalogueFetchResult listMarketCatalogue(String sessionToken, List<String> marketIds) {
        if (sessionToken == null || sessionToken.isBlank() || marketIds == null || marketIds.isEmpty()) {
            return CatalogueFetchResult.success(List.of());
        }
        ObjectNode params = objectMapper.createObjectNode();
        ObjectNode filter = objectMapper.createObjectNode();
        ArrayNode ids = objectMapper.createArrayNode();
        marketIds.forEach(ids::add);
        filter.set("marketIds", ids);
        params.set("filter", filter);
        ArrayNode projections = objectMapper.createArrayNode();
        projections.add("EVENT").add("COMPETITION").add("MARKET_START_TIME").add("RUNNER_DESCRIPTION").add("MARKET_DESCRIPTION");
        params.set("marketProjection", projections);
        params.put("maxResults", Math.min(1000, marketIds.size()));
        params.put("locale", "en");

        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("method", METHOD);
        request.set("params", params);
        request.put("id", 1);

        try {
            ResponseEntity<String> entity = restClient.post()
                    .uri(apiUrl)
                    .header("X-Application", appKey)
                    .header("X-Authentication", sessionToken)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request.toString())
                    .retrieve()
                    .toEntity(String.class);

            String body = entity.getBody();
            if (body == null || body.isBlank()) return CatalogueFetchResult.success(List.of());
            JsonNode root = objectMapper.readTree(body);
            JsonNode error = root.path("error");
            if (error != null && !error.isMissingNode()) {
                if (isTransientJsonRpcError(error)) {
                    log.warn("listMarketCatalogue JSON-RPC error (transient): {}", error);
                    return CatalogueFetchResult.transientError();
                }
                return CatalogueFetchResult.success(List.of());
            }
            JsonNode result = root.path("result");
            if (result == null || !result.isArray()) return CatalogueFetchResult.success(List.of());
            return CatalogueFetchResult.success(mapResult(result));
        } catch (org.springframework.web.client.RestClientResponseException e) {
            int code = e.getStatusCode().value();
            if (code == 429 || (code >= 500 && code < 600)) {
                log.warn("listMarketCatalogue HTTP transient: status={}", code);
                return CatalogueFetchResult.transientError();
            }
            return CatalogueFetchResult.success(List.of());
        } catch (Exception e) {
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            if (cause instanceof SocketTimeoutException || cause instanceof ConnectException) {
                log.warn("listMarketCatalogue network transient: {}", cause.getMessage());
                return CatalogueFetchResult.transientError();
            }
            log.warn("listMarketCatalogue failed: {}", e.getMessage());
            return CatalogueFetchResult.transientError();
        }
    }

    private static boolean isTransientJsonRpcError(JsonNode error) {
        String message = error.path("message").asText("");
        int code = error.path("code").asInt(0);
        return message != null && (
                message.toUpperCase().contains("TOO_MANY_REQUESTS") ||
                message.toUpperCase().contains("SERVICE_BUSY") ||
                message.toUpperCase().contains("RATE") ||
                code == 429 || code == -32099
        );
    }

    private List<MarketMetadataRecord> mapResult(JsonNode result) {
        List<MarketMetadataRecord> list = new ArrayList<>();
        for (JsonNode cat : result) {
            MarketMetadataRecord record = mapCatalogue(cat);
            if (record != null) list.add(record);
        }
        return list;
    }

    private MarketMetadataRecord mapCatalogue(JsonNode cat) {
        String marketId = cat.path("marketId").asText(null);
        if (marketId == null) return null;

        String eventId = null;
        String eventName = null;
        JsonNode event = cat.path("event");
        if (event != null && !event.isMissingNode()) {
            eventId = event.path("id").asText(null);
            eventName = event.path("name").asText(null);
        }

        String competitionId = null;
        String competitionName = null;
        JsonNode competition = cat.path("competition");
        if (competition != null && !competition.isMissingNode()) {
            competitionId = competition.path("id").asText(null);
            competitionName = competition.path("name").asText(null);
        }

        Instant marketStartTime = null;
        if (cat.has("marketStartTime") && !cat.path("marketStartTime").isNull()) {
            try {
                marketStartTime = Instant.parse(cat.path("marketStartTime").asText());
            } catch (DateTimeParseException ignored) {
            }
        }

        List<MarketMetadataRecord.RunnerInfo> runners = new ArrayList<>();
        JsonNode runnersNode = cat.path("runners");
        if (runnersNode != null && runnersNode.isArray()) {
            for (JsonNode r : runnersNode) {
                long selectionId = r.path("selectionId").asLong(-1);
                String runnerName = r.path("runnerName").asText(null);
                if (selectionId >= 0) {
                    runners.add(new MarketMetadataRecord.RunnerInfo(selectionId, runnerName));
                }
            }
        }

        String marketType = null;
        JsonNode desc = cat.path("description");
        if (desc != null && !desc.isMissingNode()) {
            marketType = desc.path("marketType").asText(null);
        }

        return MarketMetadataRecord.fromCatalogue(marketId, eventId, eventName, competitionId, competitionName, marketStartTime, runners, marketType);
    }

    /** Full-Time only: Soccer. No Half-Time. Used for priority fallback when DB has no markets. */
    private static final String[] PRIORITY_MARKET_TYPES_FT = {
            "MATCH_ODDS_FT", "OVER_UNDER_25_FT", "NEXT_GOAL"
    };

    /**
     * List soccer markets by event type and FT market types, sorted by MAXIMUM_TRADED.
     * Used as fallback when active_markets_to_stream is empty. No cap; Betfair maxResults limit applies.
     */
    public List<PriorityMarketRow> listMarketCatalogueForPriority(String sessionToken) {
        if (sessionToken == null || sessionToken.isBlank()) {
            return List.of();
        }
        ObjectNode params = objectMapper.createObjectNode();
        ObjectNode filter = objectMapper.createObjectNode();
        ArrayNode eventTypeIds = objectMapper.createArrayNode();
        eventTypeIds.add("1"); // Soccer
        filter.set("eventTypeIds", eventTypeIds);
        ArrayNode marketTypeCodes = objectMapper.createArrayNode();
        for (String mt : PRIORITY_MARKET_TYPES_FT) {
            marketTypeCodes.add(mt);
        }
        filter.set("marketTypeCodes", marketTypeCodes);
        params.set("filter", filter);
        ArrayNode projections = objectMapper.createArrayNode();
        projections.add("EVENT").add("MARKET_DESCRIPTION");
        params.set("marketProjection", projections);
        params.put("sort", "MAXIMUM_TRADED");
        params.put("maxResults", 1000);
        params.put("locale", "en");

        ObjectNode request = objectMapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("method", METHOD);
        request.set("params", params);
        request.put("id", 1);

        try {
            ResponseEntity<String> entity = restClient.post()
                    .uri(apiUrl)
                    .header("X-Application", appKey)
                    .header("X-Authentication", sessionToken)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(request.toString())
                    .retrieve()
                    .toEntity(String.class);

            String body = entity.getBody();
            if (body == null || body.isBlank()) return List.of();
            JsonNode root = objectMapper.readTree(body);
            JsonNode error = root.path("error");
            if (error != null && !error.isMissingNode()) {
                log.warn("listMarketCatalogueForPriority JSON-RPC error: {}", error);
                return List.of();
            }
            JsonNode result = root.path("result");
            if (result == null || !result.isArray()) return List.of();
            List<PriorityMarketRow> rows = new ArrayList<>();
            for (JsonNode cat : result) {
                String marketId = cat.path("marketId").asText(null);
                if (marketId == null) continue;
                String eventId = null;
                JsonNode event = cat.path("event");
                if (event != null && !event.isMissingNode()) {
                    eventId = event.path("id").asText(null);
                }
                double totalMatched = cat.path("totalMatched").asDouble(0.0);
                rows.add(new PriorityMarketRow(marketId, eventId != null ? eventId : "", totalMatched));
            }
            return rows;
        } catch (Exception e) {
            log.warn("listMarketCatalogueForPriority failed: {}", e.getMessage());
            return List.of();
        }
    }

    /** Row from listMarketCatalogue for priority resolution (event + volume). */
    public record PriorityMarketRow(String marketId, String eventId, double totalMatched) {}
}
