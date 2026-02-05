package com.netbet.streaming.metadata;

import java.time.Instant;
import java.util.List;

/**
 * Static context for a market: teams, competition, kickoff, runners.
 * Mapped from Betfair listMarketCatalogue. eventName parsed as "Home Team v Away Team" for homeTeam/awayTeam.
 * marketType from catalogue description (e.g. MATCH_ODDS) for DB filtering.
 */
public record MarketMetadataRecord(
        String marketId,
        String eventId,
        String eventName,
        String competitionId,
        String competitionName,
        Instant marketStartTime,
        List<RunnerInfo> runners,
        String homeTeam,
        String awayTeam,
        String marketType
) {
    /** selectionId + runnerName for mapping index 0/1 to specific teams. */
    public record RunnerInfo(long selectionId, String runnerName) {}

    /**
     * Build from catalogue fields; parses eventName by " v " for homeTeam and awayTeam (Betfair soccer format).
     * marketType from catalogue description (nullable).
     */
    public static MarketMetadataRecord fromCatalogue(String marketId, String eventId, String eventName,
                                                     String competitionId, String competitionName,
                                                     Instant marketStartTime, List<RunnerInfo> runners,
                                                     String marketType) {
        String homeTeam = null;
        String awayTeam = null;
        if (eventName != null && !eventName.isBlank()) {
            int v = eventName.indexOf(" v ");
            if (v > 0 && v < eventName.length() - 3) {
                homeTeam = eventName.substring(0, v).trim();
                awayTeam = eventName.substring(v + 3).trim();
            }
        }
        return new MarketMetadataRecord(
                marketId, eventId, eventName, competitionId, competitionName, marketStartTime,
                runners != null ? List.copyOf(runners) : List.of(),
                homeTeam, awayTeam, marketType
        );
    }
}
