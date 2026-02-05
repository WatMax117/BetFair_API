package com.netbet.streaming.controller;

import com.netbet.streaming.cache.MarketCache;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Simple REST endpoint to inspect the MarketCache (for debugging).
 */
@RestController
@RequestMapping("/cache")
public class CacheController {

    private final MarketCache marketCache;

    public CacheController(MarketCache marketCache) {
        this.marketCache = marketCache;
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> summary() {
        var markets = marketCache.getAllMarkets();
        Map<String, Object> result = new HashMap<>();
        result.put("marketCount", markets.size());
        result.put("marketIds", markets.keySet());
        return ResponseEntity.ok(result);
    }

    @GetMapping("/{marketId}")
    public ResponseEntity<Map<String, Object>> market(@PathVariable String marketId) {
        var market = marketCache.getMarket(marketId);
        if (market == null) {
            return ResponseEntity.notFound().build();
        }
        Map<String, Object> result = new HashMap<>();
        result.put("marketId", market.getMarketId());
        result.put("runnerCount", market.getRunners().size());
        result.put("runners", market.getRunners().entrySet().stream()
                .map(e -> Map.<String, Object>of(
                        "selectionId", e.getKey(),
                        "backLevels", e.getValue().getBackLadder(MarketCache.DEFAULT_LADDER_LEVELS).size(),
                        "layLevels", e.getValue().getLayLadder(MarketCache.DEFAULT_LADDER_LEVELS).size(),
                        "ltp", e.getValue().getLastTradedPrice(),
                        "totalMatched", e.getValue().getTotalMatched()))
                .collect(Collectors.toList()));
        return ResponseEntity.ok(result);
    }
}
