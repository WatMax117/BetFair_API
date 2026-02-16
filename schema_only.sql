--
-- PostgreSQL database dump
--

\restrict iTeoSd5Yjeh4k9dZSI2nygNc87WhHSIKfI2k1dQxsB9wAAR7swAZRZJwM1QFNcO

-- Dumped from database version 16.11
-- Dumped by pg_dump version 16.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: stream_ingest; Type: SCHEMA; Schema: -; Owner: netbet
--

CREATE SCHEMA stream_ingest;


ALTER SCHEMA stream_ingest OWNER TO netbet;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: events; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.events (
    event_id character varying(32) NOT NULL,
    event_name text,
    home_team character varying(255),
    away_team character varying(255),
    open_date timestamp with time zone
);


ALTER TABLE public.events OWNER TO netbet;

--
-- Name: flyway_schema_history; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.flyway_schema_history (
    installed_rank integer NOT NULL,
    version character varying(50),
    description character varying(200) NOT NULL,
    type character varying(20) NOT NULL,
    script character varying(1000) NOT NULL,
    checksum integer,
    installed_by character varying(100) NOT NULL,
    installed_on timestamp without time zone DEFAULT now() NOT NULL,
    execution_time integer NOT NULL,
    success boolean NOT NULL
);


ALTER TABLE public.flyway_schema_history OWNER TO netbet;

--
-- Name: ladder_levels; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.ladder_levels (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_level_check1 CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_side_check1 CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
)
PARTITION BY RANGE (publish_time);


ALTER TABLE public.ladder_levels OWNER TO netbet;

--
-- Name: ladder_levels_20260205; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.ladder_levels_20260205 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_level_check1 CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_side_check1 CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE public.ladder_levels_20260205 OWNER TO netbet;

--
-- Name: ladder_levels_20260206; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.ladder_levels_20260206 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_level_check1 CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_side_check1 CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE public.ladder_levels_20260206 OWNER TO netbet;

--
-- Name: ladder_levels_initial; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.ladder_levels_initial (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_level_check1 CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_side_check1 CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE public.ladder_levels_initial OWNER TO netbet;

--
-- Name: market_book_snapshots; Type: TABLE; Schema: public; Owner: netbet_rest_writer
--

CREATE TABLE public.market_book_snapshots (
    snapshot_id bigint NOT NULL,
    snapshot_at timestamp with time zone NOT NULL,
    market_id text NOT NULL,
    raw_payload jsonb NOT NULL,
    total_matched double precision,
    inplay boolean,
    status text,
    depth_limit integer,
    source text DEFAULT 'rest_listMarketBook'::text NOT NULL,
    capture_version text DEFAULT 'v1'::text
);


ALTER TABLE public.market_book_snapshots OWNER TO netbet_rest_writer;

--
-- Name: market_book_snapshots_snapshot_id_seq; Type: SEQUENCE; Schema: public; Owner: netbet_rest_writer
--

CREATE SEQUENCE public.market_book_snapshots_snapshot_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.market_book_snapshots_snapshot_id_seq OWNER TO netbet_rest_writer;

--
-- Name: market_book_snapshots_snapshot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netbet_rest_writer
--

ALTER SEQUENCE public.market_book_snapshots_snapshot_id_seq OWNED BY public.market_book_snapshots.snapshot_id;


--
-- Name: market_derived_metrics; Type: TABLE; Schema: public; Owner: netbet_rest_writer
--

CREATE TABLE public.market_derived_metrics (
    snapshot_id bigint NOT NULL,
    snapshot_at timestamp with time zone NOT NULL,
    market_id text NOT NULL,
    total_volume double precision NOT NULL,
    home_best_back double precision,
    away_best_back double precision,
    draw_best_back double precision,
    home_best_lay double precision,
    away_best_lay double precision,
    draw_best_lay double precision,
    home_spread double precision,
    away_spread double precision,
    draw_spread double precision,
    depth_limit integer,
    calculation_version text DEFAULT 'v1'::text,
    home_best_back_size_l1 double precision,
    away_best_back_size_l1 double precision,
    draw_best_back_size_l1 double precision,
    home_best_lay_size_l1 double precision,
    away_best_lay_size_l1 double precision,
    draw_best_lay_size_l1 double precision,
    home_book_risk_l3 double precision,
    away_book_risk_l3 double precision,
    draw_book_risk_l3 double precision,
    home_back_odds_l2 double precision,
    home_back_size_l2 double precision,
    home_back_odds_l3 double precision,
    home_back_size_l3 double precision,
    away_back_odds_l2 double precision,
    away_back_size_l2 double precision,
    away_back_odds_l3 double precision,
    away_back_size_l3 double precision,
    draw_back_odds_l2 double precision,
    draw_back_size_l2 double precision,
    draw_back_odds_l3 double precision,
    draw_back_size_l3 double precision,
    home_impedance double precision,
    away_impedance double precision,
    draw_impedance double precision,
    home_impedance_norm double precision,
    away_impedance_norm double precision,
    draw_impedance_norm double precision,
    home_back_stake double precision,
    home_back_odds double precision,
    home_lay_stake double precision,
    home_lay_odds double precision,
    away_back_stake double precision,
    away_back_odds double precision,
    away_lay_stake double precision,
    away_lay_odds double precision,
    draw_back_stake double precision,
    draw_back_odds double precision,
    draw_lay_stake double precision,
    draw_lay_odds double precision
);


ALTER TABLE public.market_derived_metrics OWNER TO netbet_rest_writer;

--
-- Name: market_event_metadata; Type: TABLE; Schema: public; Owner: netbet_rest_writer
--

CREATE TABLE public.market_event_metadata (
    market_id text NOT NULL,
    market_name text,
    market_start_time timestamp with time zone,
    sport_id text,
    sport_name text,
    event_id text,
    event_name text,
    event_open_date timestamp with time zone,
    country_code text,
    competition_id text,
    competition_name text,
    timezone text,
    home_selection_id bigint,
    away_selection_id bigint,
    draw_selection_id bigint,
    home_runner_name text,
    away_runner_name text,
    draw_runner_name text,
    metadata_version text DEFAULT 'v1'::text,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.market_event_metadata OWNER TO netbet_rest_writer;

--
-- Name: market_lifecycle_events; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.market_lifecycle_events (
    market_id character varying(32) NOT NULL,
    status character varying(32),
    in_play boolean,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL
);


ALTER TABLE public.market_lifecycle_events OWNER TO netbet;

--
-- Name: market_liquidity_history; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.market_liquidity_history (
    market_id character varying(32) NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    total_matched numeric(20,2) DEFAULT 0 NOT NULL,
    max_runner_ltp numeric(10,2)
);


ALTER TABLE public.market_liquidity_history OWNER TO netbet;

--
-- Name: market_risk_snapshots; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.market_risk_snapshots (
    market_id text NOT NULL,
    snapshot_at timestamp with time zone NOT NULL,
    home_risk double precision NOT NULL,
    away_risk double precision NOT NULL,
    draw_risk double precision NOT NULL,
    total_volume double precision NOT NULL,
    raw_payload jsonb,
    home_best_back double precision,
    away_best_back double precision,
    draw_best_back double precision,
    home_best_lay double precision,
    away_best_lay double precision,
    draw_best_lay double precision,
    depth_limit integer,
    calculation_version text
);


ALTER TABLE public.market_risk_snapshots OWNER TO netbet;

--
-- Name: markets; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.markets (
    market_id character varying(32) NOT NULL,
    event_id character varying(32) NOT NULL,
    market_type character varying(64) NOT NULL,
    market_name text,
    market_start_time timestamp with time zone,
    segment character varying(32),
    total_matched numeric(20,2),
    CONSTRAINT chk_market_type CHECK (((market_type)::text = ANY ((ARRAY['MATCH_ODDS_FT'::character varying, 'OVER_UNDER_25_FT'::character varying, 'HALF_TIME_RESULT'::character varying, 'OVER_UNDER_05_HT'::character varying, 'NEXT_GOAL'::character varying])::text[])))
);


ALTER TABLE public.markets OWNER TO netbet;

--
-- Name: runners; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.runners (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    runner_name text
);


ALTER TABLE public.runners OWNER TO netbet;

--
-- Name: seen_markets; Type: TABLE; Schema: public; Owner: netbet_rest_writer
--

CREATE TABLE public.seen_markets (
    market_id text NOT NULL,
    tick_id_first bigint NOT NULL,
    tick_id_last bigint NOT NULL,
    last_seen_at_utc timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.seen_markets OWNER TO netbet_rest_writer;

--
-- Name: tracked_markets; Type: TABLE; Schema: public; Owner: netbet_rest_writer
--

CREATE TABLE public.tracked_markets (
    market_id text NOT NULL,
    event_id text,
    event_start_time_utc timestamp with time zone NOT NULL,
    admitted_at_utc timestamp with time zone DEFAULT now() NOT NULL,
    admission_score double precision,
    state text DEFAULT 'TRACKING'::text NOT NULL,
    last_polled_at_utc timestamp with time zone,
    last_snapshot_at_utc timestamp with time zone,
    created_at_utc timestamp with time zone DEFAULT now() NOT NULL,
    updated_at_utc timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tracked_markets_state_check CHECK ((state = ANY (ARRAY['TRACKING'::text, 'DROPPED'::text])))
);


ALTER TABLE public.tracked_markets OWNER TO netbet_rest_writer;

--
-- Name: traded_volume; Type: TABLE; Schema: public; Owner: netbet
--

CREATE TABLE public.traded_volume (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    price double precision NOT NULL,
    size_traded double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL
);


ALTER TABLE public.traded_volume OWNER TO netbet;

--
-- Name: v_event_summary; Type: VIEW; Schema: public; Owner: netbet
--

CREATE VIEW public.v_event_summary AS
 SELECT e.event_id,
    e.event_name,
    e.home_team,
    e.away_team,
    m1.market_id AS match_odds_market_id,
    m1.market_name AS match_odds_market_name,
    m2.market_id AS over_under_25_market_id,
    m2.market_name AS over_under_25_market_name,
    m3.market_id AS half_time_market_id,
    m3.market_name AS half_time_market_name,
    m4.market_id AS over_under_05_ht_market_id,
    m4.market_name AS over_under_05_ht_market_name,
    m5.market_id AS next_goal_market_id,
    m5.market_name AS next_goal_market_name
   FROM (((((public.events e
     LEFT JOIN ( SELECT DISTINCT ON (markets.event_id) markets.event_id,
            markets.market_id,
            markets.market_name
           FROM public.markets
          WHERE ((markets.market_type)::text = 'MATCH_ODDS_FT'::text)
          ORDER BY markets.event_id, markets.market_start_time, markets.market_id) m1 ON (((m1.event_id)::text = (e.event_id)::text)))
     LEFT JOIN ( SELECT DISTINCT ON (markets.event_id) markets.event_id,
            markets.market_id,
            markets.market_name
           FROM public.markets
          WHERE ((markets.market_type)::text = 'OVER_UNDER_25_FT'::text)
          ORDER BY markets.event_id, markets.market_start_time, markets.market_id) m2 ON (((m2.event_id)::text = (e.event_id)::text)))
     LEFT JOIN ( SELECT DISTINCT ON (markets.event_id) markets.event_id,
            markets.market_id,
            markets.market_name
           FROM public.markets
          WHERE ((markets.market_type)::text = 'HALF_TIME_RESULT'::text)
          ORDER BY markets.event_id, markets.market_start_time, markets.market_id) m3 ON (((m3.event_id)::text = (e.event_id)::text)))
     LEFT JOIN ( SELECT DISTINCT ON (markets.event_id) markets.event_id,
            markets.market_id,
            markets.market_name
           FROM public.markets
          WHERE ((markets.market_type)::text = 'OVER_UNDER_05_HT'::text)
          ORDER BY markets.event_id, markets.market_start_time, markets.market_id) m4 ON (((m4.event_id)::text = (e.event_id)::text)))
     LEFT JOIN ( SELECT DISTINCT ON (markets.event_id) markets.event_id,
            markets.market_id,
            markets.market_name
           FROM public.markets
          WHERE ((markets.market_type)::text = 'NEXT_GOAL'::text)
          ORDER BY markets.event_id, markets.market_start_time, markets.market_id) m5 ON (((m5.event_id)::text = (e.event_id)::text)));


ALTER VIEW public.v_event_summary OWNER TO netbet;

--
-- Name: v_golden_audit; Type: VIEW; Schema: public; Owner: netbet
--

CREATE VIEW public.v_golden_audit AS
 WITH market_stats AS (
         SELECT ladder_levels.market_id,
            count(*) AS total_ladder_rows,
            count(DISTINCT ROW(ladder_levels.publish_time, ladder_levels.received_time)) AS distinct_snapshots
           FROM public.ladder_levels
          GROUP BY ladder_levels.market_id
        )
 SELECT e.event_name,
    m.segment,
    sum(ms.total_ladder_rows) AS total_ladder_rows,
    sum(ms.distinct_snapshots) AS total_distinct_snapshots,
    sum(m.total_matched) AS current_volume
   FROM ((public.events e
     JOIN public.markets m ON (((e.event_id)::text = (m.event_id)::text)))
     JOIN market_stats ms ON (((m.market_id)::text = (ms.market_id)::text)))
  GROUP BY e.event_name, m.segment;


ALTER VIEW public.v_golden_audit OWNER TO netbet;

--
-- Name: v_market_top_prices; Type: VIEW; Schema: public; Owner: netbet
--

CREATE VIEW public.v_market_top_prices AS
 SELECT market_id,
    selection_id,
    publish_time,
    received_time,
    max(
        CASE
            WHEN ((side = 'B'::bpchar) AND (level = 0)) THEN price
            ELSE NULL::double precision
        END) AS best_back_price,
    max(
        CASE
            WHEN ((side = 'B'::bpchar) AND (level = 0)) THEN size
            ELSE NULL::double precision
        END) AS best_back_size,
    max(
        CASE
            WHEN ((side = 'L'::bpchar) AND (level = 0)) THEN price
            ELSE NULL::double precision
        END) AS best_lay_price,
    max(
        CASE
            WHEN ((side = 'L'::bpchar) AND (level = 0)) THEN size
            ELSE NULL::double precision
        END) AS best_lay_size
   FROM public.ladder_levels
  GROUP BY market_id, selection_id, publish_time, received_time;


ALTER VIEW public.v_market_top_prices OWNER TO netbet;

--
-- Name: ladder_levels; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
)
PARTITION BY RANGE (publish_time);


ALTER TABLE stream_ingest.ladder_levels OWNER TO netbet;

--
-- Name: ladder_levels_20260216; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260216 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260216 OWNER TO netbet;

--
-- Name: ladder_levels_20260217; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260217 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260217 OWNER TO netbet;

--
-- Name: ladder_levels_20260218; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260218 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260218 OWNER TO netbet;

--
-- Name: ladder_levels_20260219; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260219 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260219 OWNER TO netbet;

--
-- Name: ladder_levels_20260220; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260220 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260220 OWNER TO netbet;

--
-- Name: ladder_levels_20260221; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260221 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260221 OWNER TO netbet;

--
-- Name: ladder_levels_20260222; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260222 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260222 OWNER TO netbet;

--
-- Name: ladder_levels_20260223; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260223 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260223 OWNER TO netbet;

--
-- Name: ladder_levels_20260224; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260224 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260224 OWNER TO netbet;

--
-- Name: ladder_levels_20260225; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260225 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260225 OWNER TO netbet;

--
-- Name: ladder_levels_20260226; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260226 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260226 OWNER TO netbet;

--
-- Name: ladder_levels_20260227; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260227 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260227 OWNER TO netbet;

--
-- Name: ladder_levels_20260228; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260228 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260228 OWNER TO netbet;

--
-- Name: ladder_levels_20260301; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260301 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260301 OWNER TO netbet;

--
-- Name: ladder_levels_20260302; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260302 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260302 OWNER TO netbet;

--
-- Name: ladder_levels_20260303; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260303 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260303 OWNER TO netbet;

--
-- Name: ladder_levels_20260304; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260304 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260304 OWNER TO netbet;

--
-- Name: ladder_levels_20260305; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260305 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260305 OWNER TO netbet;

--
-- Name: ladder_levels_20260306; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260306 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260306 OWNER TO netbet;

--
-- Name: ladder_levels_20260307; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260307 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260307 OWNER TO netbet;

--
-- Name: ladder_levels_20260308; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260308 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260308 OWNER TO netbet;

--
-- Name: ladder_levels_20260309; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260309 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260309 OWNER TO netbet;

--
-- Name: ladder_levels_20260310; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260310 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260310 OWNER TO netbet;

--
-- Name: ladder_levels_20260311; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260311 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260311 OWNER TO netbet;

--
-- Name: ladder_levels_20260312; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260312 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260312 OWNER TO netbet;

--
-- Name: ladder_levels_20260313; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260313 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260313 OWNER TO netbet;

--
-- Name: ladder_levels_20260314; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260314 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260314 OWNER TO netbet;

--
-- Name: ladder_levels_20260315; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260315 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260315 OWNER TO netbet;

--
-- Name: ladder_levels_20260316; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260316 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260316 OWNER TO netbet;

--
-- Name: ladder_levels_20260317; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260317 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260317 OWNER TO netbet;

--
-- Name: ladder_levels_20260318; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_20260318 (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_20260318 OWNER TO netbet;

--
-- Name: ladder_levels_initial; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.ladder_levels_initial (
    market_id character varying(32) NOT NULL,
    selection_id bigint NOT NULL,
    side character(1) NOT NULL,
    level smallint NOT NULL,
    price double precision NOT NULL,
    size double precision NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    received_time timestamp with time zone NOT NULL,
    CONSTRAINT ladder_levels_new_level_check CHECK (((level >= 0) AND (level <= 7))),
    CONSTRAINT ladder_levels_new_side_check CHECK ((side = ANY (ARRAY['B'::bpchar, 'L'::bpchar])))
);


ALTER TABLE stream_ingest.ladder_levels_initial OWNER TO netbet;

--
-- Name: market_liquidity_history; Type: TABLE; Schema: stream_ingest; Owner: netbet
--

CREATE TABLE stream_ingest.market_liquidity_history (
    market_id character varying(32) NOT NULL,
    publish_time timestamp with time zone NOT NULL,
    total_matched numeric(20,2) DEFAULT 0 NOT NULL,
    max_runner_ltp numeric(10,2)
);


ALTER TABLE stream_ingest.market_liquidity_history OWNER TO netbet;

--
-- Name: ladder_levels_20260205; Type: TABLE ATTACH; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels ATTACH PARTITION public.ladder_levels_20260205 FOR VALUES FROM ('2026-02-05 00:00:00+00') TO ('2026-02-06 00:00:00+00');


--
-- Name: ladder_levels_20260206; Type: TABLE ATTACH; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels ATTACH PARTITION public.ladder_levels_20260206 FOR VALUES FROM ('2026-02-06 00:00:00+00') TO ('2026-02-07 00:00:00+00');


--
-- Name: ladder_levels_initial; Type: TABLE ATTACH; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels ATTACH PARTITION public.ladder_levels_initial FOR VALUES FROM ('2020-01-01 00:00:00+00') TO ('2026-02-05 00:00:00+00');


--
-- Name: ladder_levels_20260216; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260216 FOR VALUES FROM ('2026-02-16 00:00:00+00') TO ('2026-02-17 00:00:00+00');


--
-- Name: ladder_levels_20260217; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260217 FOR VALUES FROM ('2026-02-17 00:00:00+00') TO ('2026-02-18 00:00:00+00');


--
-- Name: ladder_levels_20260218; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260218 FOR VALUES FROM ('2026-02-18 00:00:00+00') TO ('2026-02-19 00:00:00+00');


--
-- Name: ladder_levels_20260219; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260219 FOR VALUES FROM ('2026-02-19 00:00:00+00') TO ('2026-02-20 00:00:00+00');


--
-- Name: ladder_levels_20260220; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260220 FOR VALUES FROM ('2026-02-20 00:00:00+00') TO ('2026-02-21 00:00:00+00');


--
-- Name: ladder_levels_20260221; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260221 FOR VALUES FROM ('2026-02-21 00:00:00+00') TO ('2026-02-22 00:00:00+00');


--
-- Name: ladder_levels_20260222; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260222 FOR VALUES FROM ('2026-02-22 00:00:00+00') TO ('2026-02-23 00:00:00+00');


--
-- Name: ladder_levels_20260223; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260223 FOR VALUES FROM ('2026-02-23 00:00:00+00') TO ('2026-02-24 00:00:00+00');


--
-- Name: ladder_levels_20260224; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260224 FOR VALUES FROM ('2026-02-24 00:00:00+00') TO ('2026-02-25 00:00:00+00');


--
-- Name: ladder_levels_20260225; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260225 FOR VALUES FROM ('2026-02-25 00:00:00+00') TO ('2026-02-26 00:00:00+00');


--
-- Name: ladder_levels_20260226; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260226 FOR VALUES FROM ('2026-02-26 00:00:00+00') TO ('2026-02-27 00:00:00+00');


--
-- Name: ladder_levels_20260227; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260227 FOR VALUES FROM ('2026-02-27 00:00:00+00') TO ('2026-02-28 00:00:00+00');


--
-- Name: ladder_levels_20260228; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260228 FOR VALUES FROM ('2026-02-28 00:00:00+00') TO ('2026-03-01 00:00:00+00');


--
-- Name: ladder_levels_20260301; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260301 FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-03-02 00:00:00+00');


--
-- Name: ladder_levels_20260302; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260302 FOR VALUES FROM ('2026-03-02 00:00:00+00') TO ('2026-03-03 00:00:00+00');


--
-- Name: ladder_levels_20260303; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260303 FOR VALUES FROM ('2026-03-03 00:00:00+00') TO ('2026-03-04 00:00:00+00');


--
-- Name: ladder_levels_20260304; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260304 FOR VALUES FROM ('2026-03-04 00:00:00+00') TO ('2026-03-05 00:00:00+00');


--
-- Name: ladder_levels_20260305; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260305 FOR VALUES FROM ('2026-03-05 00:00:00+00') TO ('2026-03-06 00:00:00+00');


--
-- Name: ladder_levels_20260306; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260306 FOR VALUES FROM ('2026-03-06 00:00:00+00') TO ('2026-03-07 00:00:00+00');


--
-- Name: ladder_levels_20260307; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260307 FOR VALUES FROM ('2026-03-07 00:00:00+00') TO ('2026-03-08 00:00:00+00');


--
-- Name: ladder_levels_20260308; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260308 FOR VALUES FROM ('2026-03-08 00:00:00+00') TO ('2026-03-09 00:00:00+00');


--
-- Name: ladder_levels_20260309; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260309 FOR VALUES FROM ('2026-03-09 00:00:00+00') TO ('2026-03-10 00:00:00+00');


--
-- Name: ladder_levels_20260310; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260310 FOR VALUES FROM ('2026-03-10 00:00:00+00') TO ('2026-03-11 00:00:00+00');


--
-- Name: ladder_levels_20260311; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260311 FOR VALUES FROM ('2026-03-11 00:00:00+00') TO ('2026-03-12 00:00:00+00');


--
-- Name: ladder_levels_20260312; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260312 FOR VALUES FROM ('2026-03-12 00:00:00+00') TO ('2026-03-13 00:00:00+00');


--
-- Name: ladder_levels_20260313; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260313 FOR VALUES FROM ('2026-03-13 00:00:00+00') TO ('2026-03-14 00:00:00+00');


--
-- Name: ladder_levels_20260314; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260314 FOR VALUES FROM ('2026-03-14 00:00:00+00') TO ('2026-03-15 00:00:00+00');


--
-- Name: ladder_levels_20260315; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260315 FOR VALUES FROM ('2026-03-15 00:00:00+00') TO ('2026-03-16 00:00:00+00');


--
-- Name: ladder_levels_20260316; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260316 FOR VALUES FROM ('2026-03-16 00:00:00+00') TO ('2026-03-17 00:00:00+00');


--
-- Name: ladder_levels_20260317; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260317 FOR VALUES FROM ('2026-03-17 00:00:00+00') TO ('2026-03-18 00:00:00+00');


--
-- Name: ladder_levels_20260318; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_20260318 FOR VALUES FROM ('2026-03-18 00:00:00+00') TO ('2026-03-19 00:00:00+00');


--
-- Name: ladder_levels_initial; Type: TABLE ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels ATTACH PARTITION stream_ingest.ladder_levels_initial FOR VALUES FROM ('2020-01-01 00:00:00+00') TO ('2026-02-16 00:00:00+00');


--
-- Name: market_book_snapshots snapshot_id; Type: DEFAULT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_book_snapshots ALTER COLUMN snapshot_id SET DEFAULT nextval('public.market_book_snapshots_snapshot_id_seq'::regclass);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (event_id);


--
-- Name: flyway_schema_history flyway_schema_history_pk; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.flyway_schema_history
    ADD CONSTRAINT flyway_schema_history_pk PRIMARY KEY (installed_rank);


--
-- Name: ladder_levels ladder_levels_pkey1; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels
    ADD CONSTRAINT ladder_levels_pkey1 PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260205 ladder_levels_20260205_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels_20260205
    ADD CONSTRAINT ladder_levels_20260205_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260206 ladder_levels_20260206_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels_20260206
    ADD CONSTRAINT ladder_levels_20260206_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_initial ladder_levels_initial_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.ladder_levels_initial
    ADD CONSTRAINT ladder_levels_initial_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: market_book_snapshots market_book_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_book_snapshots
    ADD CONSTRAINT market_book_snapshots_pkey PRIMARY KEY (snapshot_id);


--
-- Name: market_derived_metrics market_derived_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_derived_metrics
    ADD CONSTRAINT market_derived_metrics_pkey PRIMARY KEY (snapshot_id);


--
-- Name: market_event_metadata market_event_metadata_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_event_metadata
    ADD CONSTRAINT market_event_metadata_pkey PRIMARY KEY (market_id);


--
-- Name: market_liquidity_history market_liquidity_history_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.market_liquidity_history
    ADD CONSTRAINT market_liquidity_history_pkey PRIMARY KEY (market_id, publish_time);


--
-- Name: markets markets_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.markets
    ADD CONSTRAINT markets_pkey PRIMARY KEY (market_id);


--
-- Name: runners runners_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.runners
    ADD CONSTRAINT runners_pkey PRIMARY KEY (market_id, selection_id);


--
-- Name: seen_markets seen_markets_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.seen_markets
    ADD CONSTRAINT seen_markets_pkey PRIMARY KEY (market_id);


--
-- Name: tracked_markets tracked_markets_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.tracked_markets
    ADD CONSTRAINT tracked_markets_pkey PRIMARY KEY (market_id);


--
-- Name: traded_volume traded_volume_pkey; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.traded_volume
    ADD CONSTRAINT traded_volume_pkey PRIMARY KEY (market_id, selection_id, price, publish_time);


--
-- Name: market_lifecycle_events uq_lifecycle_market_publish_status_inplay; Type: CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.market_lifecycle_events
    ADD CONSTRAINT uq_lifecycle_market_publish_status_inplay UNIQUE (market_id, publish_time, status, in_play);


--
-- Name: ladder_levels ladder_levels_new_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels
    ADD CONSTRAINT ladder_levels_new_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260216 ladder_levels_20260216_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260216
    ADD CONSTRAINT ladder_levels_20260216_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260217 ladder_levels_20260217_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260217
    ADD CONSTRAINT ladder_levels_20260217_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260218 ladder_levels_20260218_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260218
    ADD CONSTRAINT ladder_levels_20260218_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260219 ladder_levels_20260219_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260219
    ADD CONSTRAINT ladder_levels_20260219_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260220 ladder_levels_20260220_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260220
    ADD CONSTRAINT ladder_levels_20260220_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260221 ladder_levels_20260221_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260221
    ADD CONSTRAINT ladder_levels_20260221_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260222 ladder_levels_20260222_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260222
    ADD CONSTRAINT ladder_levels_20260222_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260223 ladder_levels_20260223_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260223
    ADD CONSTRAINT ladder_levels_20260223_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260224 ladder_levels_20260224_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260224
    ADD CONSTRAINT ladder_levels_20260224_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260225 ladder_levels_20260225_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260225
    ADD CONSTRAINT ladder_levels_20260225_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260226 ladder_levels_20260226_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260226
    ADD CONSTRAINT ladder_levels_20260226_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260227 ladder_levels_20260227_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260227
    ADD CONSTRAINT ladder_levels_20260227_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260228 ladder_levels_20260228_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260228
    ADD CONSTRAINT ladder_levels_20260228_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260301 ladder_levels_20260301_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260301
    ADD CONSTRAINT ladder_levels_20260301_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260302 ladder_levels_20260302_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260302
    ADD CONSTRAINT ladder_levels_20260302_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260303 ladder_levels_20260303_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260303
    ADD CONSTRAINT ladder_levels_20260303_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260304 ladder_levels_20260304_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260304
    ADD CONSTRAINT ladder_levels_20260304_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260305 ladder_levels_20260305_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260305
    ADD CONSTRAINT ladder_levels_20260305_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260306 ladder_levels_20260306_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260306
    ADD CONSTRAINT ladder_levels_20260306_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260307 ladder_levels_20260307_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260307
    ADD CONSTRAINT ladder_levels_20260307_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260308 ladder_levels_20260308_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260308
    ADD CONSTRAINT ladder_levels_20260308_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260309 ladder_levels_20260309_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260309
    ADD CONSTRAINT ladder_levels_20260309_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260310 ladder_levels_20260310_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260310
    ADD CONSTRAINT ladder_levels_20260310_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260311 ladder_levels_20260311_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260311
    ADD CONSTRAINT ladder_levels_20260311_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260312 ladder_levels_20260312_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260312
    ADD CONSTRAINT ladder_levels_20260312_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260313 ladder_levels_20260313_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260313
    ADD CONSTRAINT ladder_levels_20260313_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260314 ladder_levels_20260314_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260314
    ADD CONSTRAINT ladder_levels_20260314_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260315 ladder_levels_20260315_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260315
    ADD CONSTRAINT ladder_levels_20260315_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260316 ladder_levels_20260316_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260316
    ADD CONSTRAINT ladder_levels_20260316_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260317 ladder_levels_20260317_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260317
    ADD CONSTRAINT ladder_levels_20260317_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_20260318 ladder_levels_20260318_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_20260318
    ADD CONSTRAINT ladder_levels_20260318_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: ladder_levels_initial ladder_levels_initial_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.ladder_levels_initial
    ADD CONSTRAINT ladder_levels_initial_pkey PRIMARY KEY (market_id, selection_id, side, level, publish_time);


--
-- Name: market_liquidity_history market_liquidity_history_pkey; Type: CONSTRAINT; Schema: stream_ingest; Owner: netbet
--

ALTER TABLE ONLY stream_ingest.market_liquidity_history
    ADD CONSTRAINT market_liquidity_history_pkey PRIMARY KEY (market_id, publish_time);


--
-- Name: flyway_schema_history_s_idx; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX flyway_schema_history_s_idx ON public.flyway_schema_history USING btree (success);


--
-- Name: idx_ladder_market_selection_time; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_ladder_market_selection_time ON ONLY public.ladder_levels USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: idx_lifecycle_market_time; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_lifecycle_market_time ON public.market_lifecycle_events USING btree (market_id, publish_time DESC);


--
-- Name: idx_market_liquidity_history_market_id; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_market_liquidity_history_market_id ON public.market_liquidity_history USING btree (market_id);


--
-- Name: idx_market_liquidity_history_publish_time; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_market_liquidity_history_publish_time ON public.market_liquidity_history USING btree (publish_time DESC);


--
-- Name: idx_market_risk_snapshots_market_id; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_market_risk_snapshots_market_id ON public.market_risk_snapshots USING btree (market_id);


--
-- Name: idx_market_risk_snapshots_market_snapshot; Type: INDEX; Schema: public; Owner: netbet
--

CREATE UNIQUE INDEX idx_market_risk_snapshots_market_snapshot ON public.market_risk_snapshots USING btree (market_id, snapshot_at);


--
-- Name: idx_market_risk_snapshots_snapshot_at; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_market_risk_snapshots_snapshot_at ON public.market_risk_snapshots USING btree (snapshot_at);


--
-- Name: idx_markets_event_id; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_markets_event_id ON public.markets USING btree (event_id);


--
-- Name: idx_mbs_market_id; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mbs_market_id ON public.market_book_snapshots USING btree (market_id);


--
-- Name: idx_mbs_market_snapshot_unique; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE UNIQUE INDEX idx_mbs_market_snapshot_unique ON public.market_book_snapshots USING btree (market_id, snapshot_at);


--
-- Name: idx_mbs_snapshot_at; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mbs_snapshot_at ON public.market_book_snapshots USING btree (snapshot_at);


--
-- Name: idx_mdm_market_snapshot; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mdm_market_snapshot ON public.market_derived_metrics USING btree (market_id, snapshot_at);


--
-- Name: idx_mem_competition_name; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mem_competition_name ON public.market_event_metadata USING btree (competition_name);


--
-- Name: idx_mem_event_open_date; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mem_event_open_date ON public.market_event_metadata USING btree (event_open_date);


--
-- Name: idx_mem_market_start_time; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_mem_market_start_time ON public.market_event_metadata USING btree (market_start_time);


--
-- Name: idx_seen_markets_tick_last; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_seen_markets_tick_last ON public.seen_markets USING btree (tick_id_last);


--
-- Name: idx_tracked_markets_event_start; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_tracked_markets_event_start ON public.tracked_markets USING btree (event_start_time_utc);


--
-- Name: idx_tracked_markets_state; Type: INDEX; Schema: public; Owner: netbet_rest_writer
--

CREATE INDEX idx_tracked_markets_state ON public.tracked_markets USING btree (state);


--
-- Name: idx_traded_volume_market_time; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX idx_traded_volume_market_time ON public.traded_volume USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260205_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX ladder_levels_20260205_market_id_selection_id_publish_time_idx ON public.ladder_levels_20260205 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260206_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX ladder_levels_20260206_market_id_selection_id_publish_time_idx ON public.ladder_levels_20260206 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_initial_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: public; Owner: netbet
--

CREATE INDEX ladder_levels_initial_market_id_selection_id_publish_time_idx ON public.ladder_levels_initial USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: idx_ladder_market_selection_time; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX idx_ladder_market_selection_time ON ONLY stream_ingest.ladder_levels USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: idx_stream_liquidity_market_id; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX idx_stream_liquidity_market_id ON stream_ingest.market_liquidity_history USING btree (market_id);


--
-- Name: idx_stream_liquidity_publish_time; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX idx_stream_liquidity_publish_time ON stream_ingest.market_liquidity_history USING btree (publish_time DESC);


--
-- Name: ladder_levels_20260216_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260216_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260216 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260217_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260217_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260217 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260218_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260218_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260218 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260219_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260219_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260219 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260220_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260220_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260220 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260221_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260221_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260221 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260222_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260222_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260222 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260223_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260223_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260223 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260224_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260224_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260224 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260225_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260225_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260225 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260226_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260226_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260226 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260227_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260227_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260227 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260228_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260228_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260228 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260301_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260301_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260301 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260302_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260302_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260302 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260303_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260303_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260303 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260304_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260304_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260304 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260305_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260305_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260305 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260306_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260306_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260306 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260307_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260307_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260307 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260308_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260308_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260308 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260309_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260309_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260309 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260310_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260310_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260310 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260311_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260311_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260311 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260312_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260312_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260312 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260313_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260313_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260313 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260314_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260314_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260314 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260315_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260315_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260315 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260316_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260316_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260316 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260317_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260317_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260317 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260318_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_20260318_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_20260318 USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_initial_market_id_selection_id_publish_time_idx; Type: INDEX; Schema: stream_ingest; Owner: netbet
--

CREATE INDEX ladder_levels_initial_market_id_selection_id_publish_time_idx ON stream_ingest.ladder_levels_initial USING btree (market_id, selection_id, publish_time DESC);


--
-- Name: ladder_levels_20260205_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.idx_ladder_market_selection_time ATTACH PARTITION public.ladder_levels_20260205_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260205_pkey; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.ladder_levels_pkey1 ATTACH PARTITION public.ladder_levels_20260205_pkey;


--
-- Name: ladder_levels_20260206_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.idx_ladder_market_selection_time ATTACH PARTITION public.ladder_levels_20260206_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260206_pkey; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.ladder_levels_pkey1 ATTACH PARTITION public.ladder_levels_20260206_pkey;


--
-- Name: ladder_levels_initial_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.idx_ladder_market_selection_time ATTACH PARTITION public.ladder_levels_initial_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_initial_pkey; Type: INDEX ATTACH; Schema: public; Owner: netbet
--

ALTER INDEX public.ladder_levels_pkey1 ATTACH PARTITION public.ladder_levels_initial_pkey;


--
-- Name: ladder_levels_20260216_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260216_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260216_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260216_pkey;


--
-- Name: ladder_levels_20260217_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260217_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260217_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260217_pkey;


--
-- Name: ladder_levels_20260218_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260218_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260218_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260218_pkey;


--
-- Name: ladder_levels_20260219_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260219_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260219_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260219_pkey;


--
-- Name: ladder_levels_20260220_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260220_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260220_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260220_pkey;


--
-- Name: ladder_levels_20260221_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260221_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260221_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260221_pkey;


--
-- Name: ladder_levels_20260222_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260222_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260222_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260222_pkey;


--
-- Name: ladder_levels_20260223_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260223_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260223_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260223_pkey;


--
-- Name: ladder_levels_20260224_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260224_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260224_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260224_pkey;


--
-- Name: ladder_levels_20260225_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260225_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260225_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260225_pkey;


--
-- Name: ladder_levels_20260226_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260226_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260226_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260226_pkey;


--
-- Name: ladder_levels_20260227_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260227_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260227_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260227_pkey;


--
-- Name: ladder_levels_20260228_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260228_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260228_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260228_pkey;


--
-- Name: ladder_levels_20260301_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260301_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260301_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260301_pkey;


--
-- Name: ladder_levels_20260302_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260302_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260302_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260302_pkey;


--
-- Name: ladder_levels_20260303_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260303_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260303_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260303_pkey;


--
-- Name: ladder_levels_20260304_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260304_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260304_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260304_pkey;


--
-- Name: ladder_levels_20260305_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260305_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260305_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260305_pkey;


--
-- Name: ladder_levels_20260306_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260306_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260306_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260306_pkey;


--
-- Name: ladder_levels_20260307_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260307_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260307_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260307_pkey;


--
-- Name: ladder_levels_20260308_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260308_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260308_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260308_pkey;


--
-- Name: ladder_levels_20260309_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260309_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260309_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260309_pkey;


--
-- Name: ladder_levels_20260310_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260310_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260310_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260310_pkey;


--
-- Name: ladder_levels_20260311_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260311_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260311_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260311_pkey;


--
-- Name: ladder_levels_20260312_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260312_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260312_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260312_pkey;


--
-- Name: ladder_levels_20260313_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260313_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260313_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260313_pkey;


--
-- Name: ladder_levels_20260314_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260314_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260314_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260314_pkey;


--
-- Name: ladder_levels_20260315_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260315_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260315_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260315_pkey;


--
-- Name: ladder_levels_20260316_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260316_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260316_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260316_pkey;


--
-- Name: ladder_levels_20260317_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260317_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260317_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260317_pkey;


--
-- Name: ladder_levels_20260318_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_20260318_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_20260318_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_20260318_pkey;


--
-- Name: ladder_levels_initial_market_id_selection_id_publish_time_idx; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.idx_ladder_market_selection_time ATTACH PARTITION stream_ingest.ladder_levels_initial_market_id_selection_id_publish_time_idx;


--
-- Name: ladder_levels_initial_pkey; Type: INDEX ATTACH; Schema: stream_ingest; Owner: netbet
--

ALTER INDEX stream_ingest.ladder_levels_new_pkey ATTACH PARTITION stream_ingest.ladder_levels_initial_pkey;


--
-- Name: market_book_snapshots market_book_snapshots_market_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_book_snapshots
    ADD CONSTRAINT market_book_snapshots_market_id_fkey FOREIGN KEY (market_id) REFERENCES public.market_event_metadata(market_id) ON DELETE CASCADE;


--
-- Name: market_derived_metrics market_derived_metrics_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netbet_rest_writer
--

ALTER TABLE ONLY public.market_derived_metrics
    ADD CONSTRAINT market_derived_metrics_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES public.market_book_snapshots(snapshot_id) ON DELETE CASCADE;


--
-- Name: markets markets_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.markets
    ADD CONSTRAINT markets_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(event_id) ON DELETE CASCADE;


--
-- Name: runners runners_market_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netbet
--

ALTER TABLE ONLY public.runners
    ADD CONSTRAINT runners_market_id_fkey FOREIGN KEY (market_id) REFERENCES public.markets(market_id) ON DELETE CASCADE;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT USAGE ON SCHEMA public TO netbet_analytics_reader;
GRANT ALL ON SCHEMA public TO netbet_rest_writer;


--
-- Name: SCHEMA stream_ingest; Type: ACL; Schema: -; Owner: netbet
--

GRANT USAGE ON SCHEMA stream_ingest TO netbet_analytics_reader;


--
-- Name: TABLE market_book_snapshots; Type: ACL; Schema: public; Owner: netbet_rest_writer
--

GRANT SELECT ON TABLE public.market_book_snapshots TO netbet_analytics_reader;


--
-- Name: TABLE market_derived_metrics; Type: ACL; Schema: public; Owner: netbet_rest_writer
--

GRANT SELECT ON TABLE public.market_derived_metrics TO netbet_analytics_reader;


--
-- Name: TABLE market_event_metadata; Type: ACL; Schema: public; Owner: netbet_rest_writer
--

GRANT SELECT ON TABLE public.market_event_metadata TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260216; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260216 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260217; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260217 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260218; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260218 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260219; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260219 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260220; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260220 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260221; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260221 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260222; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260222 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260223; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260223 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260224; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260224 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260225; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260225 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260226; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260226 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260227; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260227 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260228; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260228 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260301; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260301 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260302; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260302 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260303; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260303 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260304; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260304 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260305; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260305 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260306; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260306 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260307; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260307 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260308; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260308 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260309; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260309 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260310; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260310 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260311; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260311 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260312; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260312 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260313; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260313 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260314; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260314 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260315; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260315 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260316; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260316 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260317; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260317 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_20260318; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_20260318 TO netbet_analytics_reader;


--
-- Name: TABLE ladder_levels_initial; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.ladder_levels_initial TO netbet_analytics_reader;


--
-- Name: TABLE market_liquidity_history; Type: ACL; Schema: stream_ingest; Owner: netbet
--

GRANT SELECT ON TABLE stream_ingest.market_liquidity_history TO netbet_analytics_reader;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: netbet
--

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA public GRANT ALL ON SEQUENCES TO netbet_rest_writer;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: netbet
--

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA public GRANT ALL ON TABLES TO netbet_rest_writer;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: stream_ingest; Owner: netbet
--

ALTER DEFAULT PRIVILEGES FOR ROLE netbet IN SCHEMA stream_ingest GRANT SELECT ON TABLES TO netbet_analytics_reader;


--
-- PostgreSQL database dump complete
--

\unrestrict iTeoSd5Yjeh4k9dZSI2nygNc87WhHSIKfI2k1dQxsB9wAAR7swAZRZJwM1QFNcO

