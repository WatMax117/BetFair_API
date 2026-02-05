package com.netbet.streaming.runner;

import com.netbet.streaming.cache.MarketCache;
import com.netbet.streaming.resilience.ReconnectPolicy;
import com.netbet.streaming.session.SessionProvider;
import com.netbet.streaming.stream.StreamingClient;
import com.netbet.streaming.subscription.PriorityMarketResolver;
import com.netbet.streaming.subscription.SubscriptionManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Orchestrates stream lifecycle: obtain valid session, connect, run read loop; on failure
 * apply fresh image policy (clear cache), exponential backoff + jitter, then reconnect.
 * SessionException triggers full re-authentication (Cert Login via auth-service); every full
 * TCP/TLS reconnection triggers marketCache.clearAll() so Initial Image is always source of truth.
 */
@Component
public class StreamingRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(StreamingRunner.class);

    private final SessionProvider sessionProvider;
    private final StreamingClient streamingClient;
    private final MarketCache marketCache;
    private final SubscriptionManager subscriptionManager;
    private final PriorityMarketResolver priorityMarketResolver;
    private final int streamDurationMinutes;
    private final boolean reconnectEnabled;

    public StreamingRunner(SessionProvider sessionProvider,
                           StreamingClient streamingClient,
                           MarketCache marketCache,
                           SubscriptionManager subscriptionManager,
                           PriorityMarketResolver priorityMarketResolver,
                           @Value("${betfair.stream-duration-minutes:0}") int streamDurationMinutes,
                           @Value("${betfair.reconnect-enabled:true}") boolean reconnectEnabled) {
        this.sessionProvider = sessionProvider;
        this.streamingClient = streamingClient;
        this.marketCache = marketCache;
        this.subscriptionManager = subscriptionManager;
        this.priorityMarketResolver = priorityMarketResolver;
        this.streamDurationMinutes = streamDurationMinutes > 0 ? streamDurationMinutes : 0;
        this.reconnectEnabled = reconnectEnabled;
    }

    @Override
    public void run(String... args) {
        log.info("Starting Betfair Stream client (reconnect={}, duration={} min)",
                reconnectEnabled, streamDurationMinutes > 0 ? streamDurationMinutes : "unlimited");

        ScheduledExecutorService scheduler = null;
        if (streamDurationMinutes > 0) {
            scheduler = Executors.newSingleThreadScheduledExecutor();
            scheduler.schedule(() -> {
                log.info("Stream duration ({}) reached. Stopping...", streamDurationMinutes);
                streamingClient.stop();
                marketCache.closeCsvWritersIfOpen();
            }, streamDurationMinutes, TimeUnit.MINUTES);
        }

        ReconnectPolicy reconnectPolicy = new ReconnectPolicy();
        int attempts = 0;
        while (true) {
            try {
                if (attempts > 0) {
                    marketCache.clearAll(); // Every full TCP/TLS reconnection: Initial Image is source of truth
                }
                String token = sessionProvider.getValidSession();
                var priorityIds = priorityMarketResolver.resolvePriorityMarketIds(token);
                if (!priorityIds.isEmpty()) {
                    subscriptionManager.setPriorityMarketIds(priorityIds);
                    log.info("Subscribing to {} markets (40 events x 5 market types)", priorityIds.size());
                }
                streamingClient.run(token);
            } catch (SessionProvider.SessionException e) {
                log.error("Session unavailable (full re-authentication required): {}", e.getMessage());
                if (!reconnectEnabled) throw new RuntimeException(e);
                // Next iteration: getValidSession() triggers fresh Cert Login via auth-service
            } catch (Exception e) {
                log.error("Stream client failed: {}", e.getMessage(), e);
                if (!reconnectEnabled) throw new RuntimeException(e);
            }

            if (!reconnectEnabled) break;

            attempts++;
            try {
                long delayMs = reconnectPolicy.nextDelayMs();
                Thread.sleep(delayMs);
            } catch (InterruptedException ie) {
                Thread.currentThread().interrupt();
                break;
            }
        }

        if (scheduler != null) {
            scheduler.shutdown();
        }
        marketCache.closeCsvWritersIfOpen();
    }
}
