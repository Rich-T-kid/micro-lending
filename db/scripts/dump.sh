#!/usr/bin/env bash
set -euo pipefail

TS=$(date +"%Y%m%d_%H%M%S")
OUT="db_backup_${TS}.sql"

mysqldump --protocol=tcp -h 127.0.0.1 -P 3307 -u ml_user -pml_pass microlending > "db/${OUT}"
echo "📦 Wrote db/${OUT}"
