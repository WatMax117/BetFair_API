#!/usr/bin/env bash
# One-time on VPS: write Postgres credentials to /opt/netbet/.env for Stage 1.
# Run: cd /opt/netbet && ./scripts/vps_apply_postgres_env.sh
# Contains credentials; remove or add to .gitignore if you do not want them in repo.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
ENV_FILE="${REPO_ROOT}/.env"

# Ensure directory exists
mkdir -p "$(dirname "$ENV_FILE")"

# Remove existing Postgres credential lines so we can append the new block (preserves other vars)
if [ -f "$ENV_FILE" ]; then
  grep -v -E '^POSTGRES_(REST_WRITER|STREAM_WRITER|ANALYTICS_READER)_' "$ENV_FILE" > "${ENV_FILE}.tmp" || true
  mv "${ENV_FILE}.tmp" "$ENV_FILE"
fi

# Append the required Postgres vars
cat >> "$ENV_FILE" << 'ENVEOF'

POSTGRES_REST_WRITER_USER=netbet_rest_writer
POSTGRES_REST_WRITER_PASSWORD=REST_WRITER_117

POSTGRES_STREAM_WRITER_USER=netbet_stream_writer
POSTGRES_STREAM_WRITER_PASSWORD=STREAM_WRITER_117

POSTGRES_ANALYTICS_READER_USER=netbet_analytics_reader
POSTGRES_ANALYTICS_READER_PASSWORD=ANALYTICS_READER_117
ENVEOF

echo "Written: $ENV_FILE"
grep -E 'POSTGRES_.*_PASSWORD' "$ENV_FILE" | sed 's/=.*/=***/' || true
