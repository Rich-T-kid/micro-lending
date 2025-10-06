#!/usr/bin/env sh
set -eu

MIGRATION_DIR="db/migrations"
LOCAL_CONTAINER_NAME="${CONTAINER_NAME:-microlending-mysql}"

# ---- parse mysql URL if provided ----
parse_mysql_url () {
  url="$1"
  rest="${url#*://}"             # user:pass@host:port/db
  userpass="${rest%@*}"          # user:pass
  hostportdb="${rest#*@}"        # host:port/db
  MYSQLUSER="${userpass%%:*}"
  MYSQLPASSWORD="${userpass#*:}"
  hostport="${hostportdb%/*}"    # host:port
  MYSQLDATABASE="${hostportdb#*/}"
  MYSQLHOST="${hostport%%:*}"
  MYSQLPORT="${hostport#*:}"
}

# ---- detect target (Railway vs local) ----
CONNECT_MODE="LOCAL_DOCKER"

if [ -n "${MYSQL_PUBLIC_URL:-}" ]; then
  parse_mysql_url "$MYSQL_PUBLIC_URL"
  CONNECT_MODE="RAILWAY_PUBLIC"
elif [ -n "${MYSQL_URL:-}" ]; then
  parse_mysql_url "$MYSQL_URL"
  CONNECT_MODE="RAILWAY_URL"
elif [ -n "${RAILWAY_DATABASE_URL:-}" ]; then
  parse_mysql_url "$RAILWAY_DATABASE_URL"
  CONNECT_MODE="RAILWAY_URL"
elif [ -n "${MYSQLHOST:-}" ] && [ -n "${MYSQLPORT:-}" ] && \
     [ -n "${MYSQLUSER:-}" ] && [ -n "${MYSQLPASSWORD:-}" ] && [ -n "${MYSQLDATABASE:-}" ]; then
  CONNECT_MODE="RAILWAY_RAW"
else
  # local dev fallback: read .env (only the 3 we need)
  if [ -f ".env" ]; then
    while IFS='=' read -r key val; do
      case "$key" in
        MYSQL_DATABASE) MYSQLDATABASE=$(printf %s "$val" | tr -d '\r"') ;;
        MYSQL_USER)     MYSQLUSER=$(printf %s "$val" | tr -d '\r"') ;;
        MYSQL_PASSWORD) MYSQLPASSWORD=$(printf %s "$val" | tr -d '\r"') ;;
      esac
    done < .env
  fi
  MYSQLDATABASE="${MYSQLDATABASE:-microlending}"
  MYSQLUSER="${MYSQLUSER:-user}"
  MYSQLPASSWORD="${MYSQLPASSWORD:-pass}"
fi

echo "Mode: $CONNECT_MODE"
echo "DB: ${MYSQLDATABASE:-?} User: ${MYSQLUSER:-?} Host: ${MYSQLHOST:-local}"

MYSQL_SSL_MODE="${MYSQL_SSL_MODE:-REQUIRED}"

# ---- runners ----
mysql_exec_remote_file() {
  file="$1"
  mysql --protocol=TCP -h "$MYSQLHOST" -P "$MYSQLPORT" -u "$MYSQLUSER" -p"$MYSQLPASSWORD" \
        --ssl-mode="$MYSQL_SSL_MODE" "$MYSQLDATABASE" < "$file"
}

mysql_exec_remote_query() {
  q="$1"
  mysql -N -B --protocol=TCP -h "$MYSQLHOST" -P "$MYSQLPORT" -u "$MYSQLUSER" -p"$MYSQLPASSWORD" \
        --ssl-mode="$MYSQL_SSL_MODE" "$MYSQLDATABASE" -e "$q"
}

# Local (dev only) path; not used on Railway but kept for completeness
mysql_exec_local_file() {
  file="$1"
  docker exec -i "$LOCAL_CONTAINER_NAME" sh -c \
    "mysql -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" \"$MYSQLDATABASE\"" < "$file"
}
mysql_exec_local_query() {
  q="$1"
  docker exec -i "$LOCAL_CONTAINER_NAME" sh -c \
    "mysql -N -B -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" \"$MYSQLDATABASE\" -e \"$q\""
}

apply_file() {
  file="$1"
  case "$CONNECT_MODE" in
    RAILWAY_PUBLIC|RAILWAY_URL|RAILWAY_RAW) mysql_exec_remote_file "$file" ;;
    LOCAL_DOCKER)                           mysql_exec_local_file  "$file" ;;
  esac
}
run_query() {
  q="$1"
  case "$CONNECT_MODE" in
    RAILWAY_PUBLIC|RAILWAY_URL|RAILWAY_RAW) mysql_exec_remote_query "$q" ;;
    LOCAL_DOCKER)                           mysql_exec_local_query  "$q" ;;
  esac
}

# ---- connectivity check ----
run_query "SELECT 1;" >/dev/null 2>&1 || { echo "❌ Cannot connect to MySQL"; exit 1; }
echo "✅ Connected."

# ---- ensure migration history ----
TMPFILE="$(mktemp 2>/dev/null || echo ./__tmp_mh.sql)"
printf '%s\n' \
'CREATE TABLE IF NOT EXISTS _migration_history (' \
'  id INT PRIMARY KEY AUTO_INCREMENT,' \
'  filename VARCHAR(255) NOT NULL UNIQUE,' \
'  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP' \
') ENGINE=InnoDB;' > "$TMPFILE"
apply_file "$TMPFILE"
rm -f "$TMPFILE"

# ---- apply migrations idempotently ----
FOUND=0
# shellcheck disable=SC2012
for f in $(ls -1 "$MIGRATION_DIR"/*.sql 2>/dev/null | sort); do
  FOUND=1
  FN=$(basename "$f")
  EXISTS=$(run_query "SELECT 1 FROM _migration_history WHERE filename='${FN}' LIMIT 1;" 2>/dev/null | tr -d '\r' || true)
  if [ "$EXISTS" != "1" ]; then
    echo ">> Applying $FN"
    apply_file "$f"
    run_query "INSERT INTO _migration_history(filename) VALUES('${FN}');" >/dev/null 2>&1 || true
  else
    echo "-- Skipping $FN (already applied)"
  fi
done
[ "$FOUND" -eq 0 ] && echo "⚠️  No migration files found in $MIGRATION_DIR"

echo "🎉 Migrations complete."
