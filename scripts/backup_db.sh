#!/usr/bin/env bash
# NetBet Betfair Streaming – PostgreSQL backup: pg_dump custom format (-Fc), retain last 7 days.
# Usage: ./scripts/backup_db.sh [output_dir]
# Requires: PGHOST, PGPORT, PGUSER, PGPASSWORD (or .pgpass), PGDATABASE (default: netbet).

set -e
BACKUP_DIR="${1:-./backups}"
DB="${PGDATABASE:-netbet}"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)
DUMP="$BACKUP_DIR/netbet_${STAMP}.dump"
pg_dump -Fc -f "$DUMP" "$DB"
echo "Backup: $DUMP"
# Keep only last 7 days; wildcard netbet_*.dump matches timestamped files (e.g. netbet_20260204_120000.dump)
find "$BACKUP_DIR" -name 'netbet_*.dump' -mtime +7 -delete
