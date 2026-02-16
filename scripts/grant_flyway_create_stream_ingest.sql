-- Allow netbet_stream_writer to create Flyway history table in stream_ingest
-- Run as: cat scripts/grant_flyway_create_stream_ingest.sql | docker exec -i netbet-postgres psql -U netbet -d netbet

GRANT CREATE ON SCHEMA stream_ingest TO netbet_stream_writer;
