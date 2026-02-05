package com.netbet.streaming.resilience;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.ThreadLocalRandom;

/**
 * Exponential backoff + jitter for reconnection. Bounds: 0.5s to 30s.
 * Reference: Spec "Exponential Backoff + Jitter: Reconnection attempts ranging from 0.5s to 30s."
 */
public class ReconnectPolicy {

    private static final Logger log = LoggerFactory.getLogger(ReconnectPolicy.class);
    private static final long MIN_DELAY_MS = 500;
    private static final long MAX_DELAY_MS = 30_000;

    private int attempt;

    public ReconnectPolicy() {
        this.attempt = 0;
    }

    /**
     * Returns delay in milliseconds for the next reconnect attempt (with jitter).
     */
    public long nextDelayMs() {
        long exponential = (long) Math.min(MAX_DELAY_MS, MIN_DELAY_MS * Math.pow(2, attempt));
        long jitter = ThreadLocalRandom.current().nextLong(0, Math.min(exponential, MAX_DELAY_MS - MIN_DELAY_MS + 1));
        long delay = Math.min(MAX_DELAY_MS, MIN_DELAY_MS + exponential / 2 + jitter);
        delay = Math.max(MIN_DELAY_MS, Math.min(MAX_DELAY_MS, delay));
        attempt++;
        log.info("Reconnect attempt {}: waiting {} ms (backoff + jitter)", attempt, delay);
        return delay;
    }

    public void reset() {
        attempt = 0;
    }
}
