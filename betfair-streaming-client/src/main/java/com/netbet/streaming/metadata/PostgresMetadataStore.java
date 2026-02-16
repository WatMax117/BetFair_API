package com.netbet.streaming.metadata;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Set;

/**
 * Persists hydrated market metadata to PostgreSQL. Called after successful listMarketCatalogue
 * (from MarketMetadataHydrator worker thread). Persists only the 5 allowed market types.
 */
@Component
@ConditionalOnProperty(name = "betfair.postgres-sink.enabled", havingValue = "true")
public class PostgresMetadataStore {

    private static final Logger log = LoggerFactory.getLogger(PostgresMetadataStore.class);
    private static final Set<String> ALLOWED_MARKET_TYPES = Set.of(
            "MATCH_ODDS_FT", "OVER_UNDER_25_FT", "HALF_TIME_RESULT", "OVER_UNDER_05_HT", "NEXT_GOAL"
    );
    private static final java.util.Map<String, String> CATALOGUE_TO_DB_MARKET_TYPE = java.util.Map.of(
            "MATCH_ODDS", "MATCH_ODDS_FT",
            "OVER_UNDER_25", "OVER_UNDER_25_FT",
            "HALF_TIME", "HALF_TIME_RESULT",
            "OVER_UNDER_05", "OVER_UNDER_05_HT",
            "OVER_UNDER_05_HT", "OVER_UNDER_05_HT",
            "NEXT_GOAL", "NEXT_GOAL"
    );
    /** Segment mapping for analytical layer (strict, non-redundant). */
    private static final java.util.Map<String, String> MARKET_TYPE_TO_SEGMENT = java.util.Map.of(
            "MATCH_ODDS_FT", "1X2_FT",
            "OVER_UNDER_25_FT", "OU_FT",
            "OVER_UNDER_05_HT", "OU_HT",
            "HALF_TIME_RESULT", "HT_LOGIC",
            "NEXT_GOAL", "NEXT_GOAL"
    );

    // Schema-qualified SQL to ensure metadata writes go to public schema (not stream_ingest)
    private static final String INSERT_EVENT = "INSERT INTO public.events (event_id, event_name, home_team, away_team, open_date) VALUES (?, ?, ?, ?, ?) ON CONFLICT (event_id) DO NOTHING";
    private static final String INSERT_MARKET = "INSERT INTO public.markets (market_id, event_id, market_type, segment, market_name, market_start_time, total_matched) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (market_id) DO UPDATE SET segment = COALESCE(EXCLUDED.segment, public.markets.segment), total_matched = COALESCE(EXCLUDED.total_matched, public.markets.total_matched)";
    private static final String INSERT_RUNNER = "INSERT INTO public.runners (market_id, selection_id, runner_name) VALUES (?, ?, ?) ON CONFLICT (market_id, selection_id) DO NOTHING";

    private final JdbcTemplate jdbc;

    public PostgresMetadataStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Persist metadata for a single market. Call from hydrator after successful fetch.
     * Persists only if marketType maps to one of the 5 allowed DB values. Does not block the streaming thread.
     */
    public void persist(MarketMetadataRecord record) {
        if (record == null || record.marketId() == null || record.eventId() == null) return;
        String dbMarketType = normalizeMarketType(record.marketType());
        if (dbMarketType == null || !ALLOWED_MARKET_TYPES.contains(dbMarketType)) return;
        try {
            Instant startTime = record.marketStartTime();
            java.sql.Timestamp startTs = startTime != null ? Timestamp.from(startTime) : null;
            String segment = MARKET_TYPE_TO_SEGMENT.getOrDefault(dbMarketType, null);
            jdbc.update(INSERT_EVENT,
                    record.eventId(),
                    record.eventName(),
                    record.homeTeam(),
                    record.awayTeam(),
                    startTs);
            jdbc.update(INSERT_MARKET,
                    record.marketId(),
                    record.eventId(),
                    dbMarketType,
                    segment,
                    record.eventName(),
                    startTs,
                    null /* total_matched from catalogue not used */);
            for (MarketMetadataRecord.RunnerInfo r : record.runners()) {
                jdbc.update(INSERT_RUNNER, record.marketId(), r.selectionId(), r.runnerName());
            }
            log.debug("Persisted metadata marketId={} eventId={} marketType={}", record.marketId(), record.eventId(), dbMarketType);
        } catch (Exception e) {
            Throwable cause = e.getCause() != null ? e.getCause() : e;
            log.warn("Failed to persist metadata marketId={}: {} - {}", record.marketId(), e.getMessage(), cause.getMessage());
        }
    }

    private static String normalizeMarketType(String catalogueMarketType) {
        if (catalogueMarketType == null || catalogueMarketType.isBlank()) return null;
        return CATALOGUE_TO_DB_MARKET_TYPE.get(catalogueMarketType.trim().toUpperCase());
    }
}
