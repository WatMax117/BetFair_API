package com.netbet.streaming.stream;

import com.netbet.streaming.router.MessageRouter;
import com.netbet.streaming.subscription.SubscriptionManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Dedicated TCP/TLS handler for Betfair Stream API.
 * Single-threaded read loop with zero blocking operations (no I/O or DB inside the loop).
 * Max line length guard to prevent memory overflows from corrupted/malformed frames.
 * Reference: Betfair Exchange Stream API - Connection, Basic Message Protocol.
 */
@Component
public class StreamingClient {

    private static final Logger log = LoggerFactory.getLogger(StreamingClient.class);
    private static final String CRLF = "\r\n";
    /** Default max line length (2MB) for priority subscription snapshots; guard against corrupted frames. */
    private static final int DEFAULT_MAX_LINE_BYTES = 2 * 1024 * 1024;

    private final String streamHost;
    private final int streamPort;
    private final int maxLineBytes;
    private final String appKey;
    private final MessageRouter messageRouter;
    private final SubscriptionManager subscriptionManager;

    private SSLSocket socket;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private PrintWriter writer;

    public StreamingClient(
            @Value("${betfair.stream-host:stream-api.betfair.com}") String streamHost,
            @Value("${betfair.stream-port:443}") int streamPort,
            @Value("${betfair.max-line-bytes:2097152}") int maxLineBytes,
            @Value("${betfair.app-key}") String appKey,
            MessageRouter messageRouter,
            SubscriptionManager subscriptionManager) {
        this.streamHost = streamHost;
        this.streamPort = streamPort;
        this.maxLineBytes = maxLineBytes > 0 ? maxLineBytes : DEFAULT_MAX_LINE_BYTES;
        this.appKey = appKey;
        this.messageRouter = messageRouter;
        this.subscriptionManager = subscriptionManager;
    }

    /**
     * Connect, authenticate, send subscription, and run the read loop on the current thread.
     * Caller must provide a valid session token (from SessionProvider).
     * No I/O or DB is performed inside the read loop—only parse and route.
     */
    public void run(String sessionToken) throws IOException {
        if (sessionToken == null || sessionToken.isBlank()) {
            throw new IllegalArgumentException("Session token must be non-null and non-blank");
        }

        SSLSocketFactory factory = (SSLSocketFactory) SSLSocketFactory.getDefault();
        socket = (SSLSocket) factory.createSocket(streamHost, streamPort);
        socket.setKeepAlive(true);

        running.set(true);
        log.info("Connected to {}:{}", streamHost, streamPort);

        try (OutputStream out = socket.getOutputStream();
             BufferedReader reader = new BufferedReader(
                     new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8))) {

            writer = new PrintWriter(out, true, StandardCharsets.UTF_8);

            send(StreamMessages.authentication(1, sessionToken, appKey));
            for (String payload : subscriptionManager.getInitialSubscriptionPayloads()) {
                send(payload);
            }

            String line;
            while (running.get() && (line = readLineWithLimit(reader)) != null) {
                long receivedTime = System.currentTimeMillis();
                messageRouter.route(line, receivedTime);
            }
        } finally {
            running.set(false);
            writer = null;
            closeSocket();
        }
    }

    /**
     * On reconnection: send resubscribe payload(s) (same filters, optional initialClk/clk).
     * Call only when already connected and writer is set (e.g. from a reconnection flow that reuses or re-establishes connection).
     */
    public void sendResubscribe() {
        if (writer != null && running.get()) {
            for (String payload : subscriptionManager.getResubscribePayloads()) {
                send(payload);
            }
        }
    }

    public void stop() {
        running.set(false);
        closeSocket();
    }

    private void closeSocket() {
        if (socket != null && !socket.isClosed()) {
            try {
                socket.close();
            } catch (IOException e) {
                log.warn("Error closing socket: {}", e.getMessage());
            }
            socket = null;
        }
    }

    private void send(String json) {
        if (writer != null) {
            writer.print(json);
            writer.print(CRLF);
            writer.flush();
        }
    }

    public boolean isRunning() {
        return running.get();
    }

    /**
     * Read a CRLF-delimited line with max length guard. Prevents memory overflow from corrupted/malformed payloads.
     * If line exceeds maxLineBytes, logs ERROR and returns null to break the loop (trigger reconnect).
     */
    private String readLineWithLimit(BufferedReader reader) throws IOException {
        StringBuilder sb = new StringBuilder(4096);
        int c;
        while ((c = reader.read()) != -1) {
            if (c == '\r') {
                int next = reader.read();
                if (next == '\n') {
                    return sb.toString();
                }
                sb.append((char) c);
                if (next != -1) sb.append((char) next);
                continue;
            }
            if (c == '\n') {
                return sb.toString();
            }
            sb.append((char) c);
            if (sb.length() > maxLineBytes) {
                log.error("Frame exceeded max line length ({} bytes). Corrupted or malformed payload; breaking connection to reconnect.",
                        maxLineBytes);
                running.set(false);
                return null;
            }
        }
        return sb.length() > 0 ? sb.toString() : null;
    }
}
