package com.netbet.streaming.subscription;

import com.netbet.streaming.metadata.BettingApiClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Fallback when active_markets_to_stream is empty: listMarketCatalogue for Soccer (FT only),
 * sort by MAXIMUM_TRADED. Returns all market IDs returned by API (no 40/200 cap). Batching for stream is done in SubscriptionManager.
 */
@Component
public class PriorityMarketResolver {

    private static final Logger log = LoggerFactory.getLogger(PriorityMarketResolver.class);

    private final BettingApiClient bettingApiClient;
    private final boolean enabled;

    public PriorityMarketResolver(BettingApiClient bettingApiClient,
                                  @Value("${betfair.priority-subscription-enabled:true}") boolean enabled) {
        this.bettingApiClient = bettingApiClient;
        this.enabled = enabled;
    }

    /**
     * Returns all market IDs from listMarketCatalogue (Soccer, FT only). No cap; batching for stream is done elsewhere.
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
        List<String> marketIds = rows.stream()
                .map(BettingApiClient.PriorityMarketRow::marketId)
                .filter(id -> id != null && !id.isBlank())
                .distinct()
                .toList();
        Set<String> eventIds = rows.stream()
                .map(BettingApiClient.PriorityMarketRow::eventId)
                .filter(id -> id != null && !id.isBlank())
                .collect(Collectors.toSet());
        log.info("Priority fallback: {} events, {} market IDs (FT only)", eventIds.size(), marketIds.size());
        return marketIds;
    }
}
