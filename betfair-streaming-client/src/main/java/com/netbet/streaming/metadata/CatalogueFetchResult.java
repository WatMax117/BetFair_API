package com.netbet.streaming.metadata;

import java.util.List;

/**
 * Result of listMarketCatalogue call. Distinguishes transient errors (retry) from empty results (putMissing).
 */
public record CatalogueFetchResult(
        List<MarketMetadataRecord> records,
        boolean isTransientError
) {
    public static CatalogueFetchResult success(List<MarketMetadataRecord> records) {
        return new CatalogueFetchResult(records != null ? records : List.of(), false);
    }

    public static CatalogueFetchResult transientError() {
        return new CatalogueFetchResult(List.of(), true);
    }
}
