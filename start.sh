#!/usr/bin/env sh
set -eu
sh db/scripts/migrate.sh
echo "✅ Migrations finished"
# keep container healthy
sleep infinity
