package com.netbet.streaming.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Loads configuration from /opt/netbet/auth-service/.env when present (e.g. on VPS).
 * Sets System properties for Betfair keys so application.yml placeholders resolve.
 * Does not override existing system properties or env vars.
 */
@Configuration
public class EnvConfig {

    private static final Logger log = LoggerFactory.getLogger(EnvConfig.class);
    private static final Pattern ENV_LINE = Pattern.compile("^([A-Za-z_][A-Za-z0-9_]*)=(.*)$");

    @Value("${betfair.env-path:/opt/netbet/auth-service/.env}")
    private String envPath;

    @PostConstruct
    public void loadEnvIfPresent() {
        Path path = Path.of(envPath);
        if (!Files.isRegularFile(path)) {
            log.debug("No .env file at {} (optional)", envPath);
            return;
        }
        try {
            List<String> lines = Files.readAllLines(path);
            int count = 0;
            for (String line : lines) {
                String trimmed = line.trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#")) continue;
                var m = ENV_LINE.matcher(trimmed);
                if (m.matches()) {
                    String key = m.group(1);
                    String value = m.group(2).trim();
                    if (value.startsWith("\"") && value.endsWith("\"")) {
                        value = value.substring(1, value.length() - 1).replace("\\\"", "\"");
                    } else if (value.startsWith("'") && value.endsWith("'")) {
                        value = value.substring(1, value.length() - 1);
                    }
                    if (System.getProperty(key) == null) {
                        System.setProperty(key, value);
                        count++;
                    }
                }
            }
            if (count > 0) {
                log.info("Loaded {} keys from {}", count, envPath);
            }
        } catch (IOException e) {
            log.warn("Could not read .env at {}: {}", envPath, e.getMessage());
        }
    }
}
