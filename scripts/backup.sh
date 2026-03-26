#!/bin/bash
# Automated Postgres backup for Memoriant Patent Platform
# Run via cron: 0 2 * * * /path/to/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/memoriant-patent}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="${CONTAINER_NAME:-memoriant-patent-platform-supabase-db-1}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# Postgres dump
docker exec "$CONTAINER_NAME" pg_dump -U postgres -Fc > "$BACKUP_DIR/patent_platform_$TIMESTAMP.dump"

# Qdrant snapshot
curl -s -X POST "http://localhost:6333/collections/patent_embeddings/snapshots" > /dev/null 2>&1 || echo "Warning: Qdrant snapshot failed (collection may not exist yet)"

# Cleanup old backups
find "$BACKUP_DIR" -name "patent_platform_*.dump" -mtime +"$RETENTION_DAYS" -delete

echo "[$(date)] Backup complete: $BACKUP_DIR/patent_platform_$TIMESTAMP.dump"
