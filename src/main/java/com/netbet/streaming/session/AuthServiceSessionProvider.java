package com.netbet.streaming.session;

import com.netbet.streaming.client.TokenClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * SessionProvider that obtains a valid token from the auth-service (Cert Login + KeepAlive).
 * Guarantees a valid token before any connection attempt; fails fast with SessionException otherwise.
 */
@Component
public class AuthServiceSessionProvider implements SessionProvider {

    private static final Logger log = LoggerFactory.getLogger(AuthServiceSessionProvider.class);

    private final TokenClient tokenClient;

    public AuthServiceSessionProvider(TokenClient tokenClient) {
        this.tokenClient = tokenClient;
    }

    @Override
    public String getValidSession() throws SessionException {
        String token = tokenClient.fetchToken();
        if (token == null || token.isBlank()) {
            throw new SessionException("Failed to obtain session token from auth-service");
        }
        log.debug("Valid session token obtained");
        return token;
    }
}
