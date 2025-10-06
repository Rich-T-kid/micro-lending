#!/usr/bin/env bash
set -euo pipefail

# This script resets the local development database by destroying the old container
# and volume data, starting a fresh container, and applying migrations.

# Load environment variables (ensure root password, user, pass, db are set)
source .env 2>/dev/null || true

# 1. Stop and remove container/volume
echo "⬇️ Tearing down existing containers and volumes..."
docker compose down -v
echo "⬆️ Starting fresh container..."
docker compose up -d

# 2. The migrate script now handles the container readiness check
# FIX: Use the explicit relative path to the migrate script
bash db/scripts/migrate.sh

# Optional demo seed
if [ -f db/seed/demo_data.sql ]; then
  echo ">> Seeding demo data"
  # For now, let's assume the migrated database user credentials work for the seed:
  if [ -z "${MYSQL_USER}" ]; then
      echo "Cannot seed demo data: MYSQL_USER is not defined in .env"
  else
    # Assuming standard MySQL client is available locally and connecting via exposed port 3307
    mysql --protocol=tcp -h 127.0.0.1 -P 3307 -u "$MYSQL_USER" "-p$MYSQL_PASSWORD" "$MYSQL_DATABASE" < db/seed/demo_data.sql
  fi
fi

echo "✅ Local DB reset & seeded."
