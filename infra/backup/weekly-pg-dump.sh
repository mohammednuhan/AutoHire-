#!/bin/sh
set -eu

RETENTION_WEEKS="${BACKUP_RETENTION_WEEKS:-4}"

while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  file="/backups/autohire-${stamp}.dump"

  PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    --host="${POSTGRES_HOST:-postgres}" \
    --port="${POSTGRES_PORT:-5432}" \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --format=custom \
    --file="${file}"

  find /backups -name "autohire-*.dump" -type f -mtime "+$((RETENTION_WEEKS * 7))" -delete
  sleep 604800
done
