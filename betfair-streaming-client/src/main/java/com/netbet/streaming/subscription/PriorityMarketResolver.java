package com.netbet.streaming.subscription;

import com.netbet.streaming.metadata.BettingApiClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Resolves "40 events x 5 markets" priority subscription: listMarketCatalogue for Soccer,
 * sort by MAXIMUM_TRADED, group by event, take top 40 events, collect up to 200 market IDs.
 */
@Component
public class PriorityMarketResolver {

    private static final Logger log = LoggerFactory.getLogger(PriorityMarketResolver.class);
    private static final int MAX_EVENTS = 40;
    private static final int MAX_MARKET_IDS = 200;

    private final BettingApiClient bettingApiClient;
    private final boolean enabled;

    public PriorityMarketResolver(BettingApiClient bettingApiClient,
                                  @Value("${betfair.priority-subscription-enabled:true}") boolean enabled) {
        this.bettingApiClient = bettingApiClient;
        this.enabled = enabled;
    }

    /**
     * Returns up to 200 market IDs: top 40 events (by total traded) x 5 market types.
     * Empty if disabled or API call fails.
     */
    public List<String> resolvePriorityMarketIds(String sessionToken) {
        if (!enabled || sessionToken == null || sessionToken.isBlank()) {
            return List.of();
        }
        List<BettingApiClient.PriorityMarketRow> rows = bettingApiClient.listMarketCatalogueForPriority(sessionToken);
        if (rows.isEmpty()) {
            log.warn("Priority market resolution returned no markets");
            return List.of();
        }
        // Group by eventId, sum totalMatched
        Map<String, Double> eventVolume = new LinkedHashMap<>();
        Map<String, List<String>> eventToMarkets = new LinkedHashMap<>();
        for (BettingApiClient.PriorityMarketRow row : rows) {
            String eid = row.eventId();
            if (eid == null || eid.isBlank()) continue;
            eventVolume.merge(eid, row.totalMatched(), Double::sum);
            eventToMarkets.computeIfAbsent(eid, k -> new ArrayList<>()).add(row.marketId());
        }
        // Top 40 events by volume
        List<String> topEventIds = eventVolume.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue(Comparator.reverseOrder()))
                .limit(MAX_EVENTS)
                .map(Map.Entry::getKey)
                .collect(Collectors.toList());
        List<String> marketIds = new ArrayList<>();
        for (String eventId : topEventIds) {
            List<String> markets = eventToMarkets.get(eventId);
            if (markets != null) {
                for (String mid : markets) {
                    if (marketIds.size() >= MAX_MARKET_IDS) break;
                    marketIds.add(mid);
                }
            }
            if (marketIds.size() >= MAX_MARKET_IDS) break;
        }
        log.info("Priority subscription: {} events, {} market IDs (40 events x 5 market types)", topEventIds.size(), marketIds.size());
        return marketIds;
    }
}
