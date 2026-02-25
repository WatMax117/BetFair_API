package com.netbet.streaming.cache;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * CSV writers for temporary data logging:
 * - prices_log.csv: timestamp, marketId, selectionId, side, price, size, level
 * - volume_log.csv: timestamp, marketId, selectionId, price, sizeTraded
 * - liquidity_events.csv: when price level size changes by more than 30% instantly
 */
public class CsvLoggingHandler {

    private static final Logger log = LoggerFactory.getLogger(CsvLoggingHandler.class);
    private static final double LIQUIDITY_THRESHOLD = 0.30;
    private static final String BACK = "BACK";
    private static final String LAY = "LAY";

    private final BufferedWriter pricesWriter;
    private final BufferedWriter volumeWriter;
    private final BufferedWriter liquidityWriter;
    private final Map<String, Double> previousSizes = new ConcurrentHashMap<>();

    public CsvLoggingHandler(File outputDir) throws IOException {
        outputDir = outputDir != null ? outputDir : new File(".");
        this.pricesWriter = createWriter(new File(outputDir, "prices_log.csv"),
                "timestamp,marketId,selectionId,side,price,size,level");
        this.volumeWriter = createWriter(new File(outputDir, "volume_log.csv"),
                "timestamp,marketId,selectionId,price,sizeTraded");
        this.liquidityWriter = createWriter(new File(outputDir, "liquidity_events.csv"),
                "timestamp,marketId,selectionId,side,price,oldSize,newSize,changePercent");
    }

    private static BufferedWriter createWriter(File file, String header) throws IOException {
        BufferedWriter w = new BufferedWriter(
                new OutputStreamWriter(new FileOutputStream(file, true), StandardCharsets.UTF_8));
        if (file.length() == 0) {
            w.write(header);
            w.newLine();
        }
        return w;
    }

    public void logPrice(long timestamp, String marketId, long selectionId, String side, double price, double size, int level) {
        try {
            synchronized (pricesWriter) {
                pricesWriter.write(String.format("%d,%s,%d,%s,%.2f,%.2f,%d", timestamp, escape(marketId), selectionId, side, price, size, level));
                pricesWriter.newLine();
            }
        } catch (IOException e) {
            log.warn("Failed to write prices_log: {}", e.getMessage());
        }
    }

    public void logVolume(long timestamp, String marketId, long selectionId, double price, double sizeTraded) {
        try {
            synchronized (volumeWriter) {
                volumeWriter.write(String.format("%d,%s,%d,%.2f,%.2f", timestamp, escape(marketId), selectionId, price, sizeTraded));
                volumeWriter.newLine();
            }
        } catch (IOException e) {
            log.warn("Failed to write volume_log: {}", e.getMessage());
        }
    }

    public void logPriceLevelChange(String marketId, long selectionId, String side, double price, int level, double oldSize, double newSize) {
        if (oldSize <= 0) return;
        double changePercent = Math.abs(newSize - oldSize) / oldSize;
        if (changePercent > LIQUIDITY_THRESHOLD) {
            long ts = System.currentTimeMillis();
            try {
                synchronized (liquidityWriter) {
                    liquidityWriter.write(String.format("%d,%s,%d,%s,%.2f,%.2f,%.2f,%.2f", ts, escape(marketId), selectionId, side, price, oldSize, newSize, changePercent * 100));
                    liquidityWriter.newLine();
                }
            } catch (IOException e) {
                log.warn("Failed to write liquidity_events: {}", e.getMessage());
            }
        }
    }

    public void checkAndLogLiquidityEvent(String marketId, long selectionId, String side, double price, int level, double oldSize, double newSize) {
        if (newSize <= 0) return;
        String k = key(marketId, selectionId, side, price, level);
        Double prev = previousSizes.put(k, newSize);
        if (prev != null && prev > 0) {
            logPriceLevelChange(marketId, selectionId, side, price, level, prev, newSize);
        }
    }

    private static String key(String marketId, long selectionId, String side, double price, int level) {
        return marketId + "|" + selectionId + "|" + side + "|" + price + "|" + level;
    }

    private static String escape(String s) {
        if (s == null) return "";
        if (s.contains(",") || s.contains("\"")) {
            return "\"" + s.replace("\"", "\"\"") + "\"";
        }
        return s;
    }

    public void close() {
        try {
            pricesWriter.close();
        } catch (IOException e) {
            log.warn("Error closing prices_log: {}", e.getMessage());
        }
        try {
            volumeWriter.close();
        } catch (IOException e) {
            log.warn("Error closing volume_log: {}", e.getMessage());
        }
        try {
            liquidityWriter.close();
        } catch (IOException e) {
            log.warn("Error closing liquidity_events: {}", e.getMessage());
        }
    }
}
