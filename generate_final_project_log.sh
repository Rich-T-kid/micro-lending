#!/bin/bash

# Final Project Submission Log 
# MicroLending Analytics Platform

OUTPUT_FILE="FINAL_PROJECT_SUBMISSION.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

DB_HOST="micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASS="micropass"
DB_NAME="microlending"
API_BASE="http://localhost:8000"

echo "Generating log..."

# Check prerequisites
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT 1" >/dev/null 2>&1 || { echo "ERROR: MySQL"; exit 1; }
redis-cli ping >/dev/null 2>&1 || { echo "ERROR: Redis"; exit 1; }
curl -s "${API_BASE}/health" >/dev/null 2>&1 && API_AVAILABLE=true || API_AVAILABLE=false

# Initialize output
cat > "$OUTPUT_FILE" << EOF
FINAL PROJECT SUBMISSION LOG
MicroLending Analytics Platform
Generated: $TIMESTAMP
Students: Saksham Mehta, Jose Lamela, Richard Baah


PART 1: ANALYTICS / REPORTING DATABASE & ETL


REQUIREMENT 1: REPORTING SCHEMA DESIGN
2+ fact tables, 4+ dimension tables, star schema design

EOF

# Helper functions
run_sql() {
    echo ">> $1" >> "$OUTPUT_FILE"
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "$2" 2>/dev/null >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
}

run_cmd() {
    echo ">> $1" >> "$OUTPUT_FILE"
    eval "$2" 2>/dev/null >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
}

# REQUIREMENT 1
run_sql "Fact Tables" "SHOW TABLES LIKE 'fact%';"
run_sql "Dimension Tables" "SHOW TABLES LIKE 'dim%';"
run_sql "fact_loan_transactions Structure" "DESCRIBE fact_loan_transactions;"
run_sql "Fact Table Row Counts" "SELECT 'fact_loan_transactions' as table_name, COUNT(*) as row_count FROM fact_loan_transactions UNION ALL SELECT 'fact_daily_portfolio', COUNT(*) FROM fact_daily_portfolio;"
run_sql "Dimension Table Row Counts" "SELECT 'dim_date' as table_name, COUNT(*) as row_count FROM dim_date UNION ALL SELECT 'dim_user', COUNT(*) FROM dim_user UNION ALL SELECT 'dim_loan_product', COUNT(*) FROM dim_loan_product UNION ALL SELECT 'dim_currency', COUNT(*) FROM dim_currency UNION ALL SELECT 'dim_loan_status', COUNT(*) FROM dim_loan_status;"
run_sql "Fact Table Partitioning" "SELECT PARTITION_NAME, PARTITION_DESCRIPTION as range_value FROM INFORMATION_SCHEMA.PARTITIONS WHERE TABLE_NAME = 'fact_loan_transactions' AND TABLE_SCHEMA = 'microlending' AND PARTITION_NAME IS NOT NULL;"
run_sql "Sample Fact Data" "SELECT transaction_key, date_key, loan_id, transaction_type, principal_amount, interest_rate FROM fact_loan_transactions ORDER BY transaction_key DESC LIMIT 5;"
run_sql "dim_user (SCD Type 2)" "SELECT user_key, user_id, email, role, credit_tier, is_current FROM dim_user WHERE is_current = TRUE LIMIT 5;"
run_sql "dim_loan_status" "SELECT * FROM dim_loan_status;"

# REQUIREMENT 2
cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 2: THREE SOURCE SYSTEMS
ETL extracts from Transaction DB, Reference Data, Market Data

EOF

run_sql "Source 1 - Transaction Database (OLTP)" "SELECT 'user' as table_name, COUNT(*) as row_count FROM user UNION ALL SELECT 'loan', COUNT(*) FROM loan UNION ALL SELECT 'loan_application', COUNT(*) FROM loan_application UNION ALL SELECT 'wallet_account', COUNT(*) FROM wallet_account;"
run_sql "Source 2 - Reference Data" "SELECT 'ref_currency' as table_name, COUNT(*) as row_count FROM ref_currency UNION ALL SELECT 'ref_loan_product', COUNT(*) FROM ref_loan_product UNION ALL SELECT 'ref_region', COUNT(*) FROM ref_region UNION ALL SELECT 'ref_credit_tier', COUNT(*) FROM ref_credit_tier;"
run_sql "Source 3 - Market Data" "SELECT 'market_fx_rates' as table_name, COUNT(*) as row_count FROM market_fx_rates UNION ALL SELECT 'market_interest_benchmarks', COUNT(*) FROM market_interest_benchmarks UNION ALL SELECT 'market_credit_spreads', COUNT(*) FROM market_credit_spreads;"
run_sql "Sample FX Rates" "SELECT base_currency, quote_currency, rate, rate_date FROM market_fx_rates ORDER BY rate_date DESC LIMIT 5;"
run_sql "Sample Interest Benchmarks" "SELECT benchmark_code, rate, effective_date, term_months FROM market_interest_benchmarks ORDER BY effective_date DESC LIMIT 5;"

# REQUIREMENT 3
cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 3: ETL PIPELINE DESIGN
Full load, incremental load with watermarks, bulk loading

EOF

run_sql "ETL Control Tables" "SHOW TABLES LIKE 'etl%';"
run_sql "ETL Watermarks" "SELECT source_name, table_name, column_name, watermark_value FROM etl_watermarks ORDER BY source_name, table_name;"
run_sql "Recent ETL Runs" "SELECT run_id, run_type, status, rows_extracted, rows_transformed, rows_loaded, started_at FROM etl_run_log ORDER BY run_id DESC LIMIT 3;"
run_sql "ETL Step Details" "SELECT step_name, step_type, status, rows_processed, duration_seconds FROM etl_step_log ORDER BY step_id DESC LIMIT 5;"
run_sql "Bulk Load Performance" "SELECT step_name, rows_processed, duration_seconds, ROUND(rows_processed/NULLIF(duration_seconds,0), 1) as rows_per_sec FROM etl_step_log WHERE step_type = 'load' ORDER BY step_id DESC LIMIT 3;"

# REQUIREMENT 4
cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 4: STORED PROCEDURES WITH ERROR HANDLING
SPs return status/error messages, surface validation failures

EOF

run_sql "ETL Stored Procedures" "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = 'microlending' AND ROUTINE_NAME LIKE 'sp_etl%';"
run_sql "Validation - Valid Record" "CALL sp_etl_validate_loan(1, 1, 5000.00, 12.5, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"
run_sql "Validation - Invalid Interest Rate (150%)" "CALL sp_etl_validate_loan(1, 1, 5000.00, 150.0, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"
run_sql "Validation - Invalid Borrower (ID 99999)" "CALL sp_etl_validate_loan(1, 99999, 5000.00, 12.5, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"
run_sql "ETL Error Log Schema" "DESCRIBE etl_error_log;"
run_sql "Processing Metrics" "SELECT run_id, run_type, rows_extracted, rows_loaded, TIMESTAMPDIFF(SECOND, started_at, completed_at) as duration_secs, ROUND(rows_loaded / NULLIF(TIMESTAMPDIFF(SECOND, started_at, completed_at), 0), 1) as rows_per_sec FROM etl_run_log ORDER BY run_id DESC LIMIT 3;"

# REQUIREMENT 5
cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 5: DATA QUALITY CHECKS
Null checks, range validation, referential integrity

EOF

run_sql "Null Value Check" "SELECT 'loan.borrower_id nulls' as check_item, COUNT(*) as violation_count FROM loan WHERE borrower_id IS NULL UNION ALL SELECT 'loan.principal nulls', COUNT(*) FROM loan WHERE principal_amount IS NULL UNION ALL SELECT 'user.email nulls', COUNT(*) FROM user WHERE email IS NULL;"
run_sql "Range Validation" "SELECT 'interest_rate > 100' as violation, COUNT(*) as violation_count FROM loan WHERE interest_rate > 100 UNION ALL SELECT 'principal <= 0', COUNT(*) FROM loan WHERE principal_amount <= 0 UNION ALL SELECT 'term_months <= 0', COUNT(*) FROM loan WHERE term_months <= 0;"
run_sql "Referential Integrity" "SELECT 'orphan loans (no user)' as check_item, COUNT(*) as violation_count FROM loan l LEFT JOIN user u ON l.borrower_id = u.id WHERE u.id IS NULL;"

# REQUIREMENT 6
cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 6: ANALYTICAL QUERIES
Star schema joins and aggregations

EOF

run_sql "Loan Distribution by Status" "SELECT ds.status_name, COUNT(*) as loan_count, SUM(f.principal_amount) as total_principal, ROUND(AVG(f.interest_rate), 2) as avg_rate FROM fact_loan_transactions f JOIN dim_loan_status ds ON f.status_key = ds.status_key GROUP BY ds.status_name ORDER BY loan_count DESC;"
run_sql "Portfolio by Month" "SELECT d.year, d.month, d.month_name, COUNT(*) as transactions, SUM(f.principal_amount) as volume FROM fact_loan_transactions f JOIN dim_date d ON f.date_key = d.date_key GROUP BY d.year, d.month, d.month_name ORDER BY d.year DESC, d.month DESC LIMIT 6;"
run_sql "Daily Portfolio Snapshot" "SELECT date_key, total_loans, active_loans, total_principal, default_rate, avg_loan_size FROM fact_daily_portfolio ORDER BY date_key DESC LIMIT 3;"

# PART 2
cat >> "$OUTPUT_FILE" << 'EOF'


PART 2: REDIS CACHE & GUI CLIENT


REQUIREMENT 7: REDIS UNDER DOCKER

EOF

run_cmd "Docker Container Status" "docker ps --filter name=redis --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'"
run_cmd "Redis Ping" "redis-cli ping"
run_cmd "Redis Version" "redis-cli INFO server | grep redis_version"
run_cmd "Docker Compose Config" "cat docker-compose.yml"

# REQUIREMENT 8-12 (API dependent)
if [ "$API_AVAILABLE" = true ]; then

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 8: CACHE-ASIDE PATTERN
On miss load from DB, on hit serve from cache

EOF

redis-cli FLUSHDB >/dev/null 2>&1
echo ">> Clear Cache: redis-cli FLUSHDB" >> "$OUTPUT_FILE"
echo "OK" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo ">> First Request (Cache Miss)" >> "$OUTPUT_FILE"
curl -s http://localhost:8000/cache/reference/currencies | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'cached: {d.get(\"cached\")}, items: {len(d.get(\"data\", []))}, ttl: {d.get(\"ttl\")}s')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo ">> Second Request (Cache Hit)" >> "$OUTPUT_FILE"
curl -s http://localhost:8000/cache/reference/currencies | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'cached: {d.get(\"cached\")}, items: {len(d.get(\"data\", []))}')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

run_cmd "Verify Redis Keys" "redis-cli KEYS 'ml:reference:*'"

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 9: CACHE INVALIDATION

EOF

echo ">> Invalidate Reference Cache" >> "$OUTPUT_FILE"
curl -s -X DELETE http://localhost:8000/cache/reference/all >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

run_cmd "Verify Cache Cleared" "redis-cli KEYS 'ml:reference:*'"

echo ">> Re-fetch After Invalidation" >> "$OUTPUT_FILE"
curl -s http://localhost:8000/cache/reference/currencies | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'cached: {d.get(\"cached\")} (fresh from DB), items: {len(d.get(\"data\", []))}')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 10: LOOK-AHEAD CACHING
Pre-cache adjacent pages for smooth scrolling

EOF

redis-cli KEYS 'ml:transactions:*' | xargs -r redis-cli DEL >/dev/null 2>&1

echo ">> Request Page 1 (Triggers Look-Ahead)" >> "$OUTPUT_FILE"
curl -s "http://localhost:8000/reporting/transactions?page=1&page_size=10" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'cached: {d.get(\"cached\")}, page: {d.get(\"page\")}, has_next: {d.get(\"has_next\")}, rows: {len(d.get(\"data\", []))}')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

run_cmd "Verify Look-Ahead Pre-cached Page 2" "redis-cli KEYS 'ml:transactions:*'"

echo ">> Request Page 2 (Cache Hit from Look-Ahead)" >> "$OUTPUT_FILE"
curl -s "http://localhost:8000/reporting/transactions?page=2&page_size=10" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'cached: {d.get(\"cached\")}, page: {d.get(\"page\")}')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 11: CACHE TELEMETRY
TTL, memory usage, hit/miss stats

EOF

run_cmd "TTL on Reference Data (1 hour)" "redis-cli TTL ml:reference:currencies"

echo ">> TTL on Transaction Pages (5 min)" >> "$OUTPUT_FILE"
TRANS_KEY=$(redis-cli KEYS 'ml:transactions:*' | head -1)
[ -n "$TRANS_KEY" ] && echo "Key: $TRANS_KEY, TTL: $(redis-cli TTL "$TRANS_KEY")" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

run_cmd "Redis Memory Usage" "redis-cli INFO memory | grep -E 'used_memory_human|used_memory_peak_human'"
run_cmd "Cache Hit/Miss Stats" "redis-cli INFO stats | grep -E 'keyspace_hits|keyspace_misses'"

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 12: PERSISTED CACHE METRICS

EOF

echo ">> Current Metrics" >> "$OUTPUT_FILE"
curl -s http://localhost:8000/cache/metrics | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d.get('totals', {})
l = d.get('latency', {})
print(f'Hits: {t.get(\"hits\")}, Misses: {t.get(\"misses\")}, Hit Ratio: {t.get(\"hit_ratio\")}%')
print(f'Avg Cache: {l.get(\"avg_cache_ms\")}ms, Avg DB: {l.get(\"avg_db_ms\")}ms, Speedup: {l.get(\"speedup_factor\")}x')
" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

run_cmd "Persisted Metrics Keys" "redis-cli KEYS 'ml:metrics:*'"
run_cmd "Hit Counts by Operation" "redis-cli HGETALL 'ml:metrics:hits:total'"
run_cmd "Miss Counts by Operation" "redis-cli HGETALL 'ml:metrics:misses:total'"

fi

cat >> "$OUTPUT_FILE" << 'EOF'

REQUIREMENT 13: GRACEFUL FALLBACK
Application continues working when Redis is unavailable.
Test: docker-compose stop redis && curl http://localhost:8000/cache/reference/currencies


END OF LOG
EOF

echo "Done: $OUTPUT_FILE"
