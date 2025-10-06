#!/bin/sh
set -eu
sh db/scripts/migrate.sh
echo "✅ Migrations finished"
# Keep container healthy in Railway
sleep infinity
