# Master Technical Specification: Java Streaming Client Refactoring

**Goal:** Refactor the Java streaming client into a production-grade system that strictly follows the official Betfair Reference Architecture (1:1 semantic alignment) for high-frequency football data collection.

---

## I. Master Technical Specification

### Core Architectural Components (Reference Standard)

- **SessionProvider**: Isolated logic for session lifecycle (Cert Login + KeepAlive). Must guarantee a valid token before any connection attempt. Implemented by `AuthServiceSessionProvider` (token from auth-service).

- **StreamingClient**: Dedicated TCP/TLS handler. Single-threaded read loop with zero blocking operations (no I/O or DB calls inside the loop). Receives token from SessionProvider and subscription payload from SubscriptionManager; delegates message handling to MessageRouter.

- **SubscriptionManager**: Handles idempotent subscription payloads. Upon reconnection, re-issues the exact same filters (soccer market types, 8-level depth). Stores `initialClk` / `clk` for optional RESUB_DELTA recovery.

- **MessageRouter & Handlers**: Centralized routing for `connection`, `status`, `heartbeat`, and `mcm` (marketChange). Handlers: ConnectionHandler, StatusHandler, HeartbeatHandler, MarketChangeHandler.

- **MarketCache (State Machine)**: Implements "Initial Image + Deltas" logic. Atomic updates at market level to prevent partial state reads. Sequence: store `clk` from change messages; on SUB_IMAGE or `img=true` replace state. **Fresh image policy**: on reconnection, cache is cleared and a new initial image is requested.

- **Sequence**: `clk` / `initialClk` stored and passed on resubscribe where applicable; status/error messages drive re-auth and reconnect.

### Data Scope & Depth (Soccer Only)

- **Markets**: FT Match Odds, FT O/U 2.5, HT Match Odds, HT O/U 0.5, Next Goal (market type codes: MATCH_ODDS, OVER_UNDER_25, HALF_TIME, OVER_UNDER_05_HT, NEXT_GOAL).
- **Order book depth**: Top 8 levels of Price + Size for both Back and Lay.
- **Metadata**: marketDefinition (inPlay, marketTime, runner status), totalMatched, ltp.

### Resilience & Recovery

- **Exponential backoff + jitter**: Reconnection attempts 0.5s–30s (ReconnectPolicy).
- **Fresh image policy**: On reconnection, cache cleared; new initial image requested.
- **Heartbeat**: Diagnostic; status/error messages drive re-auth/reconnect logic.

### Performance & Metrics

- **Latency tracking**: Delta between `publishTime` (Betfair) and `receivedTime` (local) logged (INFO when lag > 200 ms).
- **StreamEventSink**: Interface for market updates; decouples streaming from future PostgreSQL.
- **Conflation**: `conflateMs` config (default 0 or minimal) for high-volatility spikes.

### Configuration

- All parameters (App Key, token URL, cert paths via auth-service, market types, depth) loaded from environment. On VPS: `/opt/netbet/auth-service/.env` (EnvConfig).

### Non-Goals

- No database/PostgreSQL in this phase.
- No liquidity strategies or feature engineering.
- No optimizations that deviate from the Official Reference Client structure.

---

## II. Official Reference Documentation

- **Exchange Stream API**: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687396/Exchange+Stream+API  
- **Reference Guide**: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687473/Reference+Guide  
- **Java**: https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687529/Java  
- **Sample code (Java, C#, Node.js)**: https://github.com/betfair/stream-api-sample-code  
- **Stream API schema**: https://github.com/betfair/stream-api-sample-code/blob/master/ESASwaggerSchema.json  

---

## III. Acceptance Criteria

1. **Reconnection**: Exponential backoff + jitter (0.5s–30s); on reconnect, cache cleared and new initial image requested.
2. **Latency tracking**: System tracks and logs delta between publishTime and receivedTime (logged when lag > 200 ms).
3. **8-level depth**: Order book limited to top 8 levels Back/Lay; subscription and cache expose 8 levels.
4. **SessionProvider**: Valid token guaranteed before any connection attempt.
5. **StreamingClient**: Single-threaded read loop; no blocking I/O or DB in loop.
6. **SubscriptionManager**: Idempotent payloads; same filters re-issued on reconnect.
7. **MessageRouter**: Central routing for connection, status, heartbeat, mcm.
8. **MarketCache**: Initial image + deltas; atomic at market level; clk stored; clearAll on reconnect.
9. **Config**: All parameters from env / `/opt/netbet/auth-service/.env`.
10. **StreamEventSink**: Interface implemented; optional sink implementations (e.g. CSV profile, future DB).

---

## IV. Addendum to Technical Specification

### 1. Advanced Latency & Health Monitoring

- **Graduated latency alerts** (MarketChangeHandler):
  - **INFO**: Lag > 200 ms (normal network jitter).
  - **WARN**: Lag > 500 ms (potential bottleneck or local network congestion).
  - **ERROR**: Lag > 2000 ms (critical delay; data stale for high-frequency decisions).

- **Frame safety**: **Max Line Length Guard** in StreamingClient read loop (default 128 KB, configurable via `betfair.max-line-bytes`). Corrupted or malformed JSON payloads that exceed the limit are detected; the connection is broken and reconnect is triggered to prevent memory overflows.

### 2. Market State & Lifecycle Events

- **StreamEventSink** receives lifecycle events from **marketDefinition**:
  - **Status changes**: OPEN → SUSPENDED → CLOSED (passed as `status`).
  - **In-play status**: When `inPlay` becomes true (passed as `inPlay`).
- New method: `onMarketLifecycleEvent(marketId, status, inPlay, marketDefinition, receivedAt)` (default no-op).
- Rationale: Gold standard for goals, VAR interventions, and match endings in future database analysis.

### 3. Resilience Refinements

- **Session management**: SessionProvider throws **SessionException** strictly when a valid token cannot be obtained. StreamingRunner catches **SessionException** specifically and logs "full re-authentication required"; the next loop iteration calls `getValidSession()` again (Cert Login via auth-service), i.e. full re-auth instead of a simple reconnect.

- **Cache invalidation**: `marketCache.clearAll()` is triggered on **every full TCP/TLS reconnection** (when `attempts > 0` before calling `streamingClient.run(token)`), so the Initial Image is always the source of truth and delta corruption is avoided.

---

## V. Production-Safe: Security, Telemetry, Metadata (Final)

### 1. Resilience – Metadata Hydrator 2-Step Adaptive Backoff

- **Transient errors**: HTTP 429/5xx, `SocketTimeoutException`, `ConnectException`, or JSON-RPC codes such as "TOO_MANY_REQUESTS" / "SERVICE_BUSY" are treated as transient. Failed market IDs are re-queued.
- **2-step backoff**: First transient error → **5s** backoff (`first-transient-backoff-ms`, default 5000). Consecutive transient errors → **10s** backoff (`consecutive-transient-backoff-ms`, default 10000). Backoff resets to `minIntervalMs` on the first successful batch.
- **Rate-limit guard**: `min-interval-ms` (default 200ms) between successful API calls.

### 2. Security – Spring Security for /metadata/**

- **Spring Security** restricts **`/metadata/**`** to users with **ROLE_ADMIN** using **HTTP Basic** authentication.
- In-memory user: configurable via `betfair.metadata-admin-user` and `betfair.metadata-admin-password` (defaults: `admin` / `changeme`).
- **PermitAll**: `/cache/**`, `/error`, `/actuator/**`, `/**` (all other paths).
- **Production recommendation**: Restrict `/metadata/**` at the reverse proxy (e.g. Nginx) by IP allowlist or shared-secret header; see `SecurityConfig` TODO.

### 3. Telemetry (Metadata Hydrator)

- **Endpoint**: `GET /metadata/telemetry` (Basic Auth required).
- **Metrics**:
  - **total_calls**: Total `listMarketCatalogue` API calls.
  - **transient_errors**: Calls that returned a transient error.
  - **requeued_ids_total**: Total market IDs re-queued due to transient errors (API pressure indicator).
  - **resolved_metadata**: Markets successfully resolved with full metadata.
  - **resolved_missing**: Markets resolved as missing (not in catalogue).
  - **pending_queue_size**: Current queue size (on-demand `queue.size()`).
- **Burst alert**: Immediate WARN log if `transient_errors` increases by 5 since last telemetry log.

### 4. Metadata – Home v Away Parsing from listMarketCatalogue

- **MarketMetadataRecord** is built from `listMarketCatalogue` response. The **eventName** field (Betfair soccer format, e.g. `"Arsenal v Liverpool"`) is parsed to populate **homeTeam** and **awayTeam**.
- **Logic**: Split on the literal substring `" v "` (space–v–space). Text before → `homeTeam`, text after → `awayTeam`. If the pattern is not found, both remain null.
- Exposed in **GET /metadata/{marketId}** along with eventId, eventName, competitionId, competitionName, marketStartTime, and runners (selectionId + runnerName).
