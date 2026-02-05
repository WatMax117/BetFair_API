# Final Schema & Parameters Audit (V5 Analytical Layer)

**Context:** Post–V5 deployment structural verification of the analytical layer.  
**Source:** Live diagnostic queries run against `netbet-postgres` on the VPS.

---

## Step 1: Detailed Parameter Inspection (Core Tables)

| table_name                | column_name      | data_type                  | is_nullable | key_type   |
|---------------------------|------------------|----------------------------|-------------|------------|
| events                    | event_id         | character varying          | NO          | PRIMARY KEY |
| events                    | event_name       | text                       | YES         |            |
| events                    | home_team        | character varying          | YES         |            |
| events                    | away_team        | character varying          | YES         |            |
| events                    | open_date        | timestamp with time zone   | YES         |            |
| ladder_levels             | market_id        | character varying          | NO          | PRIMARY KEY |
| ladder_levels             | selection_id     | bigint                     | NO          | PRIMARY KEY |
| ladder_levels             | side             | character                  | NO          | PRIMARY KEY |
| ladder_levels             | level            | smallint                   | NO          | PRIMARY KEY |
| ladder_levels             | price            | double precision           | NO          |            |
| ladder_levels             | size             | double precision           | NO          |            |
| ladder_levels             | publish_time     | timestamp with time zone   | NO          | PRIMARY KEY |
| ladder_levels             | received_time    | timestamp with time zone   | NO          |            |
| market_liquidity_history  | market_id        | character varying          | NO          | PRIMARY KEY |
| market_liquidity_history  | publish_time     | timestamp with time zone   | NO          | PRIMARY KEY |
| market_liquidity_history  | total_matched    | numeric                    | NO          |            |
| market_liquidity_history  | max_runner_ltp   | numeric                    | YES         |            |
| markets                   | market_id        | character varying          | NO          | PRIMARY KEY |
| markets                   | event_id         | character varying          | NO          |            |
| markets                   | market_type      | character varying          | NO          |            |
| markets                   | market_name      | text                       | YES         |            |
| markets                   | market_start_time| timestamp with time zone   | YES         |            |
| markets                   | segment          | character varying          | YES         |            |
| markets                   | total_matched    | numeric                    | YES         |            |

**Total:** 24 columns across the four core tables.

---

## Step 2: Analytical View Structure (v_golden_audit)

| column_name             | data_type         |
|-------------------------|--------------------|
| event_name              | text               |
| segment                 | character varying  |
| total_ladder_rows       | numeric            |
| total_distinct_snapshots| numeric            |
| current_volume         | numeric            |

The view is active and exposes these five output parameters.

---

## Step 3: Summary – Required Parameters Confirmed

| Requirement | Expected | Actual | Status |
|-------------|----------|--------|--------|
| **markets.segment** | varchar, for ontological filtering | `character varying`, nullable | ✅ Present |
| **markets.total_matched** | numeric, latest snapshot volume | `numeric`, nullable | ✅ Present |
| **market_liquidity_history.max_runner_ltp** | numeric, price dynamics | `numeric`, nullable | ✅ Present |
| **ladder_levels structure** | publish_time and received_time in structure | **publish_time:** in composite PRIMARY KEY. **received_time:** column present (timestamp with time zone, NOT NULL). Composite PK: (market_id, selection_id, side, level, publish_time). | ✅ Confirmed |

---

## Ladder_levels Composite Key Detail

- **Primary key columns:** `market_id`, `selection_id`, `side`, `level`, `publish_time`.
- **publish_time:** part of the composite primary key.
- **received_time:** part of the table structure (non-key column, timestamp with time zone, NOT NULL).

Both `publish_time` and `received_time` are confirmed in the ladder_levels structure; `publish_time` is part of the composite key used for partitioning and uniqueness.
