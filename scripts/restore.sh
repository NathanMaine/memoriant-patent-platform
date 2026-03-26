#!/bin/bash
# Restore Memoriant Patent Platform from a Postgres backup dump.
# Usage: ./restore.sh <path-to-dump-file>
#
# Example:
#   ./restore.sh /var/backups/memoriant-patent/patent_platform_20260101_020000.dump
#
# WARNING: This will DROP and recreate the target database. Run with caution.

set -euo pipefail

DUMP_FILE="${1:-}"
CONTAINER_NAME="${CONTAINER_NAME:-memoriant-patent-platform-supabase-db-1}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-postgres}"

if [[ -z "$DUMP_FILE" ]]; then
  echo "Usage: $0 <path-to-dump-file>" >&2
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Error: dump file not found: $DUMP_FILE" >&2
  exit 1
fi

echo "[$(date)] Starting restore from: $DUMP_FILE"

# Verify the target container is running
if ! docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -q true; then
  echo "Error: container '$CONTAINER_NAME' is not running." >&2
  echo "Start the stack first: docker compose up -d supabase-db" >&2
  exit 1
fi

# Terminate existing connections to the target database
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
  > /dev/null 2>&1 || true

# Drop and recreate the database
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

# Restore from the custom-format dump
docker exec -i "$CONTAINER_NAME" pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --role="$DB_USER" < "$DUMP_FILE"

echo "[$(date)] Restore complete. Database '$DB_NAME' has been restored from $DUMP_FILE"
echo ""
echo "Next steps:"
echo "  1. Verify data integrity: docker exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c '\\dt'"
echo "  2. Restart dependent services: docker compose restart patent-api"
