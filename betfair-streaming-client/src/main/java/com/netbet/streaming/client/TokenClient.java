package com.netbet.streaming.client;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * Fetches the Betfair session token (ssoid) from the Python auth-service.
 * Auth service URL: http://158.220.83.195:8080/token
 */
@Component
public class TokenClient {

    private static final Logger log = LoggerFactory.getLogger(TokenClient.class);

    private final RestClient restClient;
    private final String tokenUrl;

    public TokenClient(
            RestClient.Builder restClientBuilder,
            @Value("${betfair.token-url:http://158.220.83.195:8080/token}") String tokenUrl) {
        this.tokenUrl = tokenUrl;
        this.restClient = restClientBuilder.build();
    }

    private static final int MAX_RETRIES = 3;
    private static final long RETRY_DELAY_MS = 2000;

    /**
     * Fetch the current valid session token from the auth service.
     * Retries up to 3 times with 2-second delay between attempts.
     *
     * @return session token (ssoid), or null if unavailable after retries
     */
    public String fetchToken() {
        for (int attempt = 1; attempt <= MAX_RETRIES; attempt++) {
            try {
                TokenResponse response = restClient.get()
                        .uri(tokenUrl)
                        .retrieve()
                        .body(TokenResponse.class);

                if (response != null && "valid".equals(response.status) && response.ssoid != null) {
                    log.debug("Token fetched successfully");
                    return response.ssoid;
                }
                log.warn("Token response invalid (attempt {}/{}): status={}",
                        attempt, MAX_RETRIES, response != null ? response.status : "null");
            } catch (Exception e) {
                log.warn("Token fetch failed (attempt {}/{}): {} - {}", attempt, MAX_RETRIES, tokenUrl, e.getMessage());
            }
            if (attempt < MAX_RETRIES) {
                try {
                    Thread.sleep(RETRY_DELAY_MS);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        log.error("Failed to fetch token after {} attempts", MAX_RETRIES);
        return null;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class TokenResponse {
        @JsonProperty("ssoid")
        public String ssoid;
        @JsonProperty("status")
        public String status;
    }
}
