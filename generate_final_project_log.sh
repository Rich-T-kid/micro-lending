#!/bin/bash

# ============================================================================
# Final Project Submission Log Generator
# MicroLending Analytics Platform
# Students: Saksham Mehta, Jose Lamela, Richard Baah
# ============================================================================

OUTPUT_FILE="FINAL_PROJECT_SUBMISSION.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Database connection details
DB_HOST="micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASS="micropass"
DB_NAME="microlending"

# API server endpoint
API_BASE="http://localhost:8000"

echo "Final Project Submission Log Generator"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check MySQL connection
if ! mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "SELECT 1" >/dev/null 2>&1; then
    echo "ERROR: Cannot connect to MySQL database"
    exit 1
fi
echo "  [OK] MySQL connection"

# Check Redis
if ! redis-cli ping >/dev/null 2>&1; then
    echo "ERROR: Redis is not running. Start with: brew services start redis"
    exit 1
fi
echo "  [OK] Redis connection"

# Check API server
if ! curl -s "${API_BASE}/health" >/dev/null 2>&1; then
    echo "WARNING: API server not running. Some tests will be skipped."
    API_AVAILABLE=false
else
    echo "  [OK] API server running"
    API_AVAILABLE=true
fi

echo ""
echo "Generating log file: $OUTPUT_FILE"
echo ""

# Initialize output file
cat > "$OUTPUT_FILE" << EOF
FINAL PROJECT SUBMISSION LOG
MicroLending Analytics Platform
Generated: $TIMESTAMP
Students: Saksham Mehta, Jose Lamela, Richard Baah

This log demonstrates all required Final Project features:
  Part 1: Analytics/Reporting Database & ETL Pipeline
  Part 2: Redis Cache & GUI Client

PART 1: ANALYTICS / REPORTING DATABASE & ETL

EOF

# Helper function to run SQL queries
run_sql() {
    local title="$1"
    local sql="$2"
    echo "" >> "$OUTPUT_FILE"
    echo "--- $title ---" >> "$OUTPUT_FILE"
    echo "Query: $sql" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$sql" 2>/dev/null >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
}

# Helper function for section headers
section() {
    echo "" >> "$OUTPUT_FILE"
    echo "$1" >> "$OUTPUT_FILE"
}

# PART 1: REPORTING SCHEMA

section "1. REPORTING SCHEMA DESIGN"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: 2+ fact tables, 4+ dimension tables, star schema design

EOF

echo "  Testing schema design..."

run_sql "1.1 Fact Tables (2 required)" \
    "SELECT 'fact_loan_transactions' as table_name, (SELECT COUNT(*) FROM fact_loan_transactions) as row_count UNION ALL SELECT 'fact_daily_portfolio', (SELECT COUNT(*) FROM fact_daily_portfolio);"

run_sql "1.2 Dimension Tables (4+ required)" \
    "SELECT 'dim_date' as table_name, (SELECT COUNT(*) FROM dim_date) as row_count UNION ALL SELECT 'dim_user', (SELECT COUNT(*) FROM dim_user) UNION ALL SELECT 'dim_loan_product', (SELECT COUNT(*) FROM dim_loan_product) UNION ALL SELECT 'dim_currency', (SELECT COUNT(*) FROM dim_currency) UNION ALL SELECT 'dim_loan_status', (SELECT COUNT(*) FROM dim_loan_status);"

run_sql "1.3 Fact Table Structure - fact_loan_transactions" \
    "DESCRIBE fact_loan_transactions;"

run_sql "1.4 Fact Table Partitioning" \
    "SELECT PARTITION_NAME, PARTITION_DESCRIPTION as range_value FROM INFORMATION_SCHEMA.PARTITIONS WHERE TABLE_NAME = 'fact_loan_transactions' AND TABLE_SCHEMA = 'microlending' AND PARTITION_NAME IS NOT NULL;"

run_sql "1.5 Sample Fact Data" \
    "SELECT transaction_key, date_key, loan_id, transaction_type, principal_amount, interest_rate, status_key FROM fact_loan_transactions ORDER BY transaction_key DESC LIMIT 5;"

run_sql "1.6 Dimension - dim_date Sample" \
    "SELECT date_key, full_date, year, month, month_name, is_weekend FROM dim_date WHERE full_date BETWEEN '2025-12-01' AND '2025-12-03';"

run_sql "1.7 Dimension - dim_user (with SCD Type 2)" \
    "SELECT user_key, user_id, email, role, credit_tier, is_current FROM dim_user WHERE is_current = TRUE LIMIT 5;"

run_sql "1.8 Dimension - dim_loan_status" \
    "SELECT * FROM dim_loan_status;"

# THREE SOURCE SYSTEMS

section "2. THREE SOURCE SYSTEMS"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: ETL extracts from Transaction DB, Reference Data, Market Data

EOF

run_sql "2.1 Source 1: OLTP Transaction Database" \
    "SELECT 'user' as table_name, COUNT(*) as rows FROM user UNION ALL SELECT 'loan', COUNT(*) FROM loan UNION ALL SELECT 'loan_application', COUNT(*) FROM loan_application UNION ALL SELECT 'wallet_account', COUNT(*) FROM wallet_account;"

run_sql "2.2 Source 2: Reference Data Tables" \
    "SELECT 'ref_currency' as table_name, COUNT(*) as rows FROM ref_currency UNION ALL SELECT 'ref_loan_product', COUNT(*) FROM ref_loan_product UNION ALL SELECT 'ref_region', COUNT(*) FROM ref_region UNION ALL SELECT 'ref_credit_tier', COUNT(*) FROM ref_credit_tier;"

run_sql "2.3 Source 3: Market Data Tables" \
    "SELECT 'market_fx_rates' as table_name, COUNT(*) as rows FROM market_fx_rates UNION ALL SELECT 'market_interest_benchmarks', COUNT(*) FROM market_interest_benchmarks UNION ALL SELECT 'market_credit_spreads', COUNT(*) FROM market_credit_spreads;"

run_sql "2.4 Sample FX Rates" \
    "SELECT base_currency, quote_currency, rate, rate_date FROM market_fx_rates ORDER BY rate_date DESC LIMIT 5;"

run_sql "2.5 Sample Interest Benchmarks" \
    "SELECT benchmark_code, rate, effective_date, term_months FROM market_interest_benchmarks ORDER BY effective_date DESC LIMIT 5;"

# ETL PIPELINE

section "3. ETL PIPELINE DESIGN"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Extract, Transform, Load with logging and error handling

EOF

run_sql "3.1 ETL Control Tables" \
    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME LIKE 'etl%' ORDER BY TABLE_NAME;"

run_sql "3.2 ETL Watermarks (Incremental Load Support)" \
    "SELECT source_name, table_name, column_name, watermark_value FROM etl_watermarks ORDER BY source_name, table_name;"

run_sql "3.3 Recent ETL Runs" \
    "SELECT run_id, run_type, status, rows_extracted, rows_transformed, rows_loaded, started_at FROM etl_run_log ORDER BY run_id DESC LIMIT 3;"

run_sql "3.4 ETL Step Details" \
    "SELECT step_name, step_type, status, rows_processed, duration_seconds FROM etl_step_log ORDER BY step_id DESC LIMIT 5;"

# STORED PROCEDURES

section "4. ETL STORED PROCEDURES"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Stored procedures with error handling and status returns

EOF

run_sql "4.1 List ETL Procedures" \
    "SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = 'microlending' AND ROUTINE_NAME LIKE 'sp_etl%';"

run_sql "4.2 Test Validation Procedure - Valid Record" \
    "CALL sp_etl_validate_loan(1, 1, 5000.00, 12.5, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"

run_sql "4.3 Test Validation Procedure - Invalid Interest Rate" \
    "CALL sp_etl_validate_loan(1, 1, 5000.00, 150.0, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"

run_sql "4.4 Test Validation Procedure - Invalid Borrower" \
    "CALL sp_etl_validate_loan(1, 99999, 5000.00, 12.5, 12, 'active', @valid, @code, @msg); SELECT @valid as is_valid, @code as error_code, @msg as message;"

# DATA QUALITY

section "5. DATA QUALITY CHECKS"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Null checks, range validation, referential integrity

EOF

run_sql "5.1 Null Value Check" \
    "SELECT 'loan.borrower_id nulls' as check_item, COUNT(*) as count FROM loan WHERE borrower_id IS NULL UNION ALL SELECT 'loan.principal nulls', COUNT(*) FROM loan WHERE principal_amount IS NULL UNION ALL SELECT 'user.email nulls', COUNT(*) FROM user WHERE email IS NULL;"

run_sql "5.2 Range Validation" \
    "SELECT 'interest_rate > 100' as violation, COUNT(*) as count FROM loan WHERE interest_rate > 100 UNION ALL SELECT 'principal <= 0', COUNT(*) FROM loan WHERE principal_amount <= 0 UNION ALL SELECT 'term_months <= 0', COUNT(*) FROM loan WHERE term_months <= 0;"

run_sql "5.3 Referential Integrity" \
    "SELECT 'orphan loans (no user)' as check_item, COUNT(*) as count FROM loan l LEFT JOIN user u ON l.borrower_id = u.id WHERE u.id IS NULL;"

# ANALYTICAL QUERIES

section "6. ANALYTICAL QUERIES"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Example queries showing schema efficiency

EOF

run_sql "6.1 Loan Distribution by Status" \
    "SELECT ds.status_name, COUNT(*) as loan_count, SUM(f.principal_amount) as total_principal, ROUND(AVG(f.interest_rate), 2) as avg_rate FROM fact_loan_transactions f JOIN dim_loan_status ds ON f.status_key = ds.status_key GROUP BY ds.status_name ORDER BY loan_count DESC;"

run_sql "6.2 Portfolio Summary by Month" \
    "SELECT d.year, d.month, d.month_name, COUNT(*) as transactions, SUM(f.principal_amount) as volume FROM fact_loan_transactions f JOIN dim_date d ON f.date_key = d.date_key GROUP BY d.year, d.month, d.month_name ORDER BY d.year DESC, d.month DESC LIMIT 6;"

run_sql "6.3 Daily Portfolio Snapshot" \
    "SELECT date_key, total_loans, active_loans, total_principal, default_rate, avg_loan_size FROM fact_daily_portfolio ORDER BY date_key DESC LIMIT 3;"

# PART 2: REDIS CACHE

cat >> "$OUTPUT_FILE" << 'EOF'

PART 2: REDIS CACHE & GUI CLIENT

EOF

section "7. REDIS SETUP"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Run Redis under Docker

EOF

echo "" >> "$OUTPUT_FILE"
echo "--- 7.1 Docker Container Status ---" >> "$OUTPUT_FILE"
echo "Command: docker ps --filter name=redis" >> "$OUTPUT_FILE"
docker ps --filter "name=redis" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 7.2 Redis Connection Test ---" >> "$OUTPUT_FILE"
echo "Command: redis-cli ping" >> "$OUTPUT_FILE"
redis-cli ping >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 7.3 Redis Version (from Docker) ---" >> "$OUTPUT_FILE"
docker exec microlending-redis redis-cli INFO server 2>&1 | grep redis_version >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "--- 7.4 Docker Compose Configuration ---" >> "$OUTPUT_FILE"
echo "File: docker-compose.yml" >> "$OUTPUT_FILE"
cat docker-compose.yml >> "$OUTPUT_FILE" 2>/dev/null
echo "" >> "$OUTPUT_FILE"

# CACHE-ASIDE PATTERN

if [ "$API_AVAILABLE" = true ]; then

section "8. CACHE-ASIDE PATTERN"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Cache miss loads from DB, cache hit serves from Redis

EOF

echo "  Testing cache patterns..."

# Clear cache for fresh test
redis-cli DEL ml:reference:currencies ml:reference:loan_types ml:reference:regions >/dev/null 2>&1

echo "" >> "$OUTPUT_FILE"
echo "--- 8.1 Cache Miss (First Request) ---" >> "$OUTPUT_FILE"
echo "Action: Cleared cache, requesting currencies" >> "$OUTPUT_FILE"
echo "Endpoint: GET /cache/reference/currencies" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
curl -s "${API_BASE}/cache/reference/currencies" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Type: {d[\"type\"]}')
print(f'Items: {len(d[\"data\"])}')
print(f'Cached: {d[\"cached\"]} <- FALSE indicates data loaded from database')
print(f'TTL: {d.get(\"ttl\", \"N/A\")}s')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 8.2 Cache Hit (Second Request) ---" >> "$OUTPUT_FILE"
echo "Action: Same request, should be cached" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
curl -s "${API_BASE}/cache/reference/currencies" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Cached: {d[\"cached\"]} <- TRUE indicates data served from Redis')
print(f'TTL remaining: {d.get(\"ttl\", \"N/A\")}s')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 8.3 Verify Redis Keys ---" >> "$OUTPUT_FILE"
echo "Command: redis-cli KEYS 'ml:reference:*'" >> "$OUTPUT_FILE"
redis-cli KEYS "ml:reference:*" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

# CACHE INVALIDATION

section "9. CACHE INVALIDATION"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Invalidate cache when reference data changes

EOF

echo "" >> "$OUTPUT_FILE"
echo "--- 9.1 Invalidate All Reference Cache ---" >> "$OUTPUT_FILE"
echo "Endpoint: DELETE /cache/reference/all" >> "$OUTPUT_FILE"
curl -s -X DELETE "${API_BASE}/cache/reference/all" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "--- 9.2 Verify Cache Cleared ---" >> "$OUTPUT_FILE"
echo "Command: redis-cli KEYS 'ml:reference:*'" >> "$OUTPUT_FILE"
KEYS=$(redis-cli KEYS "ml:reference:*" 2>&1)
if [ -z "$KEYS" ]; then
    echo "(empty - cache successfully cleared)" >> "$OUTPUT_FILE"
else
    echo "$KEYS" >> "$OUTPUT_FILE"
fi
echo "" >> "$OUTPUT_FILE"

echo "--- 9.3 Re-fetch After Invalidation ---" >> "$OUTPUT_FILE"
curl -s "${API_BASE}/cache/reference/currencies" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Cached: {d[\"cached\"]} <- FALSE (fresh load after invalidation)')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

# PAGED GRID WITH LOOK-AHEAD

section "10. PAGED GRID WITH LOOK-AHEAD CACHING"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Pre-load adjacent pages for smooth scrolling

EOF

echo "  Testing pagination with look-ahead..."

# Clear transaction cache
redis-cli KEYS "ml:transactions:*" 2>/dev/null | xargs -r redis-cli DEL >/dev/null 2>&1

echo "" >> "$OUTPUT_FILE"
echo "--- 10.1 Request Page 1 (Triggers Look-Ahead) ---" >> "$OUTPUT_FILE"
echo "Endpoint: GET /reporting/transactions?page=1&page_size=10" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
curl -s "${API_BASE}/reporting/transactions?page=1&page_size=10" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Page: {d[\"page\"]} of {d[\"total_pages\"]}')
print(f'Total Records: {d[\"total_count\"]}')
print(f'Records Returned: {len(d[\"data\"])}')
print(f'Cached: {d[\"cached\"]} <- FALSE (first request)')
print(f'Has Next Page: {d[\"has_next\"]}')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 10.2 Verify Look-Ahead Pre-cached Page 2 ---" >> "$OUTPUT_FILE"
echo "Command: redis-cli KEYS 'ml:transactions:*'" >> "$OUTPUT_FILE"
redis-cli KEYS "ml:transactions:*" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"
echo "Result: Both page 1 and page 2 should be cached" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "--- 10.3 Request Page 2 (Cache Hit) ---" >> "$OUTPUT_FILE"
curl -s "${API_BASE}/reporting/transactions?page=2&page_size=10" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Page: {d[\"page\"]}')
print(f'Cached: {d[\"cached\"]} <- TRUE (pre-cached by look-ahead)')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

echo "--- 10.4 Page Navigation Cache Hits ---" >> "$OUTPUT_FILE"
echo "Requesting page 1 again..." >> "$OUTPUT_FILE"
curl -s "${API_BASE}/reporting/transactions?page=1&page_size=10" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Page 1 Cached: {d[\"cached\"]} <- TRUE')
" >> "$OUTPUT_FILE" 2>&1
echo "" >> "$OUTPUT_FILE"

# CACHE TELEMETRY

section "11. CACHE TELEMETRY"

cat >> "$OUTPUT_FILE" << 'EOF'
Requirement: Logging, metrics, hit ratios

EOF

echo "" >> "$OUTPUT_FILE"
echo "--- 11.1 TTL on Cached Keys ---" >> "$OUTPUT_FILE"
echo "Reference Data (1 hour = 3600s):" >> "$OUTPUT_FILE"
echo "  ml:reference:currencies TTL: $(redis-cli TTL ml:reference:currencies 2>&1)s" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "Transaction Pages (5 min = 300s):" >> "$OUTPUT_FILE"
for key in $(redis-cli KEYS "ml:transactions:*" 2>/dev/null | head -2); do
    echo "  $key TTL: $(redis-cli TTL "$key" 2>&1)s" >> "$OUTPUT_FILE"
done
echo "" >> "$OUTPUT_FILE"

echo "--- 11.2 Redis Memory Stats ---" >> "$OUTPUT_FILE"
redis-cli INFO memory 2>&1 | grep -E "used_memory_human|peak_memory" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

echo "--- 11.3 Cache Hit/Miss Stats ---" >> "$OUTPUT_FILE"
redis-cli INFO stats 2>&1 | grep -E "keyspace_hits|keyspace_misses" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

fi  # End API_AVAILABLE check

# Add closing
echo "" >> "$OUTPUT_FILE"
echo "END OF FINAL PROJECT SUBMISSION LOG" >> "$OUTPUT_FILE"

echo ""
echo "Log generated successfully: $OUTPUT_FILE"
echo ""
echo "Preview (last 30 lines):"
echo ""
tail -30 "$OUTPUT_FILE"
