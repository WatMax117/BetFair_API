package com.netbet.streaming.session;

/**
 * Isolated session lifecycle for Betfair Stream API.
 * Guarantees a valid session token before any connection attempt.
 * Reference: Betfair Exchange Stream API - Authentication / Login Session Management.
 */
public interface SessionProvider {

    /**
     * Returns a valid session token. Must not return null or blank.
     * Callers must use this before opening the stream connection.
     *
     * @return non-null, non-blank session token (SSOID)
     * @throws SessionException if a valid token cannot be obtained
     */
    String getValidSession() throws SessionException;

    /** Thrown when session cannot be obtained or is invalid. */
    class SessionException extends Exception {
        public SessionException(String message) {
            super(message);
        }
        public SessionException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
