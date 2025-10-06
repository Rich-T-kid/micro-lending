#!/usr/bin/env bash
set -euo pipefail

MIGRATION_DIR="db/migrations"
LOCAL_CONTAINER_NAME="${CONTAINER_NAME:-microlending-mysql}"

# -------- helpers --------
parse_mysql_url () {
  # Accepts mysql://user:pass@host:port/db  → sets MYSQLUSER, MYSQLPASSWORD, MYSQLHOST, MYSQLPORT, MYSQLDATABASE
  local url="$1"
  local rest="${url#*://}"                 # user:pass@host:port/db
  local userpass="${rest%@*}"              # user:pass
  local hostportdb="${rest#*@}"            # host:port/db
  MYSQLUSER="${userpass%%:*}"
  MYSQLPASSWORD="${userpass#*:}"
  local hostport="${hostportdb%/*}"
  MYSQLDATABASE="${hostportdb#*/}"
  MYSQLHOST="${hostport%%:*}"
  MYSQLPORT="${hostport#*:}"
}

have() { command -v "$1" >/dev/null 2>&1; }

# -------- detect target (Railway vs local) --------
CONNECT_MODE="LOCAL_DOCKER"

# 1) Prefer Railway PUBLIC URL if available or if host is *.internal
if [[ -n "${MYSQL_PUBLIC_URL:-}" ]]; then
  parse_mysql_url "$MYSQL_PUBLIC_URL"
  CONNECT_MODE="RAILWAY_PUBLIC"
elif [[ -n "${MYSQL_URL:-}" ]]; then
  # Some Railway envs expose MYSQL_URL (often internal). If it resolves, great; otherwise still works inside Railway.
  parse_mysql_url "$MYSQL_URL"
  CONNECT_MODE="RAILWAY_URL"
elif [[ -n "${RAILWAY_DATABASE_URL:-}" ]]; then
  parse_mysql_url "$RAILWAY_DATABASE_URL"
  CONNECT_MODE="RAILWAY_URL"
elif [[ -n "${MYSQLHOST:-}" && -n "${MYSQLPORT:-}" && -n "${MYSQLUSER:-}" && -n "${MYSQLPASSWORD:-}" && -n "${MYSQLDATABASE:-}" ]]; then
  # Raw pieces provided. If host is internal and we're running locally, this may not resolve.
  CONNECT_MODE="RAILWAY_RAW"
else
  # Local dev: try .env
  if [[ -f ".env" ]]; then
    # shellcheck disable=SC2046
    export $(grep -E '^(MYSQL_DATABASE|MYSQL_USER|MYSQL_PASSWORD)=' .env | sed 's/\r$//' | xargs -n1)
  fi
  MYSQLDATABASE="${MYSQL_DATABASE:-microlending}"
  MYSQLUSER="${MYSQL_USER:-user}"
  MYSQLPASSWORD="${MYSQL_PASSWORD:-pass}"
fi

# If the host is clearly internal but a public URL exists, prefer public.
if [[ "${MYSQLHOST:-}" =~ \.internal$ && -n "${MYSQL_PUBLIC_URL:-}" ]]; then
  parse_mysql_url "$MYSQL_PUBLIC_URL"
  CONNECT_MODE="RAILWAY_PUBLIC"
fi

echo "Mode: $CONNECT_MODE"
echo "DB: ${MYSQLDATABASE:-?}  User: ${MYSQLUSER:-?}  Host: ${MYSQLHOST:-local}"

# -------- mysql runners --------
# For Railway we’ll use a throwaway mysql client container (no local mysql install needed).
MYSQL_SSL_MODE="${MYSQL_SSL_MODE:-REQUIRED}"   # Railway public endpoint typically needs TLS

mysql_exec_remote_file() {
  local file="$1"
  docker run --rm -i mysql:8.4 \
    sh -c "mysql --protocol=TCP -h \"$MYSQLHOST\" -P \"$MYSQLPORT\" -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" --ssl-mode=$MYSQL_SSL_MODE \"$MYSQLDATABASE\"" < "$file"
}

mysql_exec_remote_query() {
  local q="$1"
  docker run --rm -i mysql:8.4 \
    sh -c "mysql -N -B --protocol=TCP -h \"$MYSQLHOST\" -P \"$MYSQLPORT\" -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" --ssl-mode=$MYSQL_SSL_MODE \"$MYSQLDATABASE\" -e \"$q\""
}

mysql_exec_local_file() {
  local file="$1"
  docker exec -i "$LOCAL_CONTAINER_NAME" sh -c "mysql -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" \"$MYSQLDATABASE\"" < "$file"
}

mysql_exec_local_query() {
  local q="$1"
  docker exec -i "$LOCAL_CONTAINER_NAME" sh -c "mysql -N -B -u \"$MYSQLUSER\" -p\"$MYSQLPASSWORD\" \"$MYSQLDATABASE\" -e \"$q\""
}

apply_file() {
  case "$CONNECT_MODE" in
    RAILWAY_PUBLIC|RAILWAY_URL|RAILWAY_RAW) mysql_exec_remote_file "$1" ;;
    LOCAL_DOCKER)                           mysql_exec_local_file  "$1" ;;
  esac
}

run_query() {
  case "$CONNECT_MODE" in
    RAILWAY_PUBLIC|RAILWAY_URL|RAILWAY_RAW) mysql_exec_remote_query "$1" ;;
    LOCAL_DOCKER)                           mysql_exec_local_query  "$1" ;;
  esac
}

# -------- connectivity check --------
echo "🧪 Checking connectivity..."
run_query "SELECT 1;" >/dev/null
echo "✅ Connected."

# -------- ensure history table --------
apply_file <(cat <<'SQL'
CREATE TABLE IF NOT EXISTS _migration_history (
  id INT PRIMARY KEY AUTO_INCREMENT,
  filename VARCHAR(255) NOT NULL UNIQUE,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
SQL
)

# -------- run migrations idempotently --------
shopt -s nullglob
for f in $(ls -1 "$MIGRATION_DIR"/*.sql | sort); do
  FN=$(basename "$f")
  EXISTS=$(run_query "SELECT 1 FROM _migration_history WHERE filename='${FN}' LIMIT 1;" | tr -d '\r' || true)
  if [[ "$EXISTS" != "1" ]]; then
    echo ">> Applying $FN"
    apply_file "$f"
    run_query "INSERT INTO _migration_history(filename) VALUES('${FN}');" >/dev/null
  else
    echo "-- Skipping $FN (already applied)"
  fi
done
shopt -u nullglob

echo "🎉 Migrations complete."