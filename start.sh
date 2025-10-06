#!/usr/bin/env bash
set -euo pipefail
# Prefer public URL; fall back to MYSQL* pieces
export MYSQL_SSL_MODE="${MYSQL_SSL_MODE:-REQUIRED}"
bash db/scripts/migrate.sh
echo "✅ Migrations finished"
# keep the service alive so Railway marks it healthy
tail -f /dev/null
