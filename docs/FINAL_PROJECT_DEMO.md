# Final Project Demonstration Document - MicroLending Analytics Platform

Students: Saksham Mehta, Jose Lamela, Richard Baah  
Date: December 2025

---

## PREREQUISITES

### Start Docker (Redis)
```bash
docker-compose up -d
```

### Verify Redis is Running
```bash
docker ps --filter name=redis
```

### Start API Server
```bash
cd src/api_server
source ../../venv/bin/activate
uvicorn server:app --reload --port 8000
```

### Start Frontend GUI (New Terminal)
```bash
cd frontend
npm start
```
Frontend runs at: http://localhost:3000

### MySQL Connection
```bash
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com -u admin -pmicropass microlending
```

---

# PART 1: ANALYTICS / REPORTING DATABASE & ETL

---

## REQUIREMENT 1: REPORTING SCHEMA DESIGN (2+ Fact Tables, 4+ Dimension Tables)

### Step 1.1: Fact Tables
```sql
SHOW TABLES LIKE 'fact%';
```

### Step 1.2: Dimension Tables
```sql
SHOW TABLES LIKE 'dim%';
```

### Step 1.3: Fact Table Structure - fact_loan_transactions
```sql
DESCRIBE fact_loan_transactions;
```

### Step 1.4: Fact Table Row Counts
```sql
SELECT 'fact_loan_transactions' as table_name, COUNT(*) as rows FROM fact_loan_transactions
UNION ALL
SELECT 'fact_daily_portfolio', COUNT(*) FROM fact_daily_portfolio;
```

### Step 1.5: Dimension Table Row Counts
```sql
SELECT 'dim_date' as table_name, COUNT(*) as rows FROM dim_date
UNION ALL SELECT 'dim_user', COUNT(*) FROM dim_user
UNION ALL SELECT 'dim_loan_product', COUNT(*) FROM dim_loan_product
UNION ALL SELECT 'dim_currency', COUNT(*) FROM dim_currency
UNION ALL SELECT 'dim_loan_status', COUNT(*) FROM dim_loan_status;
```

### Step 1.6: Fact Table Partitioning
```sql
SELECT PARTITION_NAME, PARTITION_DESCRIPTION 
FROM INFORMATION_SCHEMA.PARTITIONS 
WHERE TABLE_NAME = 'fact_loan_transactions' 
AND TABLE_SCHEMA = 'microlending' 
AND PARTITION_NAME IS NOT NULL;
```

### Step 1.7: Sample Fact Data
```sql
SELECT transaction_key, date_key, loan_id, transaction_type, principal_amount, interest_rate 
FROM fact_loan_transactions 
ORDER BY transaction_key DESC LIMIT 5;
```

### Step 1.8: dim_user with SCD Type 2
```sql
SELECT user_key, user_id, email, role, credit_tier, is_current 
FROM dim_user WHERE is_current = TRUE LIMIT 5;
```

### Step 1.9: dim_loan_status
```sql
SELECT * FROM dim_loan_status;
```

---

## REQUIREMENT 2: THREE SOURCE SYSTEMS

### Step 2.1: Source 1 - Transaction Database (OLTP)
```sql
SELECT 'user' as table_name, COUNT(*) as rows FROM user
UNION ALL SELECT 'loan', COUNT(*) FROM loan
UNION ALL SELECT 'loan_application', COUNT(*) FROM loan_application
UNION ALL SELECT 'wallet_account', COUNT(*) FROM wallet_account;
```

### Step 2.2: Source 2 - Reference Data
```sql
SELECT 'ref_currency' as table_name, COUNT(*) as rows FROM ref_currency
UNION ALL SELECT 'ref_loan_product', COUNT(*) FROM ref_loan_product
UNION ALL SELECT 'ref_region', COUNT(*) FROM ref_region
UNION ALL SELECT 'ref_credit_tier', COUNT(*) FROM ref_credit_tier;
```

### Step 2.3: Source 3 - Market Data
```sql
SELECT 'market_fx_rates' as table_name, COUNT(*) as rows FROM market_fx_rates
UNION ALL SELECT 'market_interest_benchmarks', COUNT(*) FROM market_interest_benchmarks
UNION ALL SELECT 'market_credit_spreads', COUNT(*) FROM market_credit_spreads;
```

### Step 2.4: Sample FX Rates
```sql
SELECT base_currency, quote_currency, rate, rate_date 
FROM market_fx_rates ORDER BY rate_date DESC LIMIT 5;
```

### Step 2.5: Sample Interest Benchmarks
```sql
SELECT benchmark_code, rate, effective_date, term_months 
FROM market_interest_benchmarks ORDER BY effective_date DESC LIMIT 5;
```

---

## REQUIREMENT 3: ETL PIPELINE DESIGN

### Step 3.1: ETL Control Tables
```sql
SHOW TABLES LIKE 'etl%';
```

### Step 3.2: ETL Watermarks (Incremental Load Support)
```sql
SELECT source_name, table_name, column_name, watermark_value 
FROM etl_watermarks ORDER BY source_name, table_name;
```

### Step 3.3: Recent ETL Runs
```sql
SELECT run_id, run_type, status, rows_extracted, rows_transformed, rows_loaded, started_at 
FROM etl_run_log ORDER BY run_id DESC LIMIT 3;
```

### Step 3.4: ETL Step Details
```sql
SELECT step_name, step_type, status, rows_processed, duration_seconds 
FROM etl_step_log ORDER BY step_id DESC LIMIT 5;
```

### Step 3.5: Run Full ETL Load
```bash
cd reporting/etl
python run_etl.py --mode full
```

### Step 3.6: Run Incremental ETL Load
```bash
python run_etl.py --mode incremental
```

---

## REQUIREMENT 4: STORED PROCEDURES WITH ERROR HANDLING

### Step 4.1: List ETL Stored Procedures
```sql
SELECT ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES 
WHERE ROUTINE_SCHEMA = 'microlending' AND ROUTINE_NAME LIKE 'sp_etl%';
```

### Step 4.2: Test Validation - Valid Record
```sql
CALL sp_etl_validate_loan(1, 1, 5000.00, 12.5, 12, 'active', @valid, @code, @msg);
SELECT @valid as is_valid, @code as error_code, @msg as message;
```

### Step 4.3: Test Validation - Invalid Interest Rate
```sql
CALL sp_etl_validate_loan(1, 1, 5000.00, 150.0, 12, 'active', @valid, @code, @msg);
SELECT @valid as is_valid, @code as error_code, @msg as message;
```

### Step 4.4: Test Validation - Invalid Borrower
```sql
CALL sp_etl_validate_loan(1, 99999, 5000.00, 12.5, 12, 'active', @valid, @code, @msg);
SELECT @valid as is_valid, @code as error_code, @msg as message;
```

---

## REQUIREMENT 5: DATA QUALITY CHECKS

### Step 5.1: Null Value Check
```sql
SELECT 'loan.borrower_id nulls' as check_item, COUNT(*) as count FROM loan WHERE borrower_id IS NULL
UNION ALL SELECT 'loan.principal nulls', COUNT(*) FROM loan WHERE principal_amount IS NULL
UNION ALL SELECT 'user.email nulls', COUNT(*) FROM user WHERE email IS NULL;
```

### Step 5.2: Range Validation
```sql
SELECT 'interest_rate > 100' as violation, COUNT(*) as count FROM loan WHERE interest_rate > 100
UNION ALL SELECT 'principal <= 0', COUNT(*) FROM loan WHERE principal_amount <= 0
UNION ALL SELECT 'term_months <= 0', COUNT(*) FROM loan WHERE term_months <= 0;
```

### Step 5.3: Referential Integrity
```sql
SELECT 'orphan loans (no user)' as check_item, COUNT(*) as count 
FROM loan l LEFT JOIN user u ON l.borrower_id = u.id WHERE u.id IS NULL;
```

---

## REQUIREMENT 6: ANALYTICAL QUERIES

### Step 6.1: Loan Distribution by Status
```sql
SELECT ds.status_name, COUNT(*) as loan_count, SUM(f.principal_amount) as total_principal, 
       ROUND(AVG(f.interest_rate), 2) as avg_rate
FROM fact_loan_transactions f
JOIN dim_loan_status ds ON f.status_key = ds.status_key
GROUP BY ds.status_name ORDER BY loan_count DESC;
```

### Step 6.2: Portfolio by Month
```sql
SELECT d.year, d.month, d.month_name, COUNT(*) as transactions, SUM(f.principal_amount) as volume
FROM fact_loan_transactions f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year DESC, d.month DESC LIMIT 6;
```

### Step 6.3: Daily Portfolio Snapshot
```sql
SELECT date_key, total_loans, active_loans, total_principal, default_rate, avg_loan_size 
FROM fact_daily_portfolio ORDER BY date_key DESC LIMIT 3;
```

---

# PART 2: REDIS CACHE & GUI CLIENT

---

## REQUIREMENT 7: REDIS UNDER DOCKER

### Step 7.1: Docker Container Status
```bash
docker ps --filter name=redis
```

### Step 7.2: Redis Connection Test
```bash
redis-cli ping
```

### Step 7.3: Redis Version
```bash
redis-cli INFO server | grep redis_version
```

### Step 7.4: Docker Compose Configuration
```bash
cat docker-compose.yml
```

---

## REQUIREMENT 8: CACHE-ASIDE PATTERN

### Step 8.1: Clear Cache
```bash
redis-cli FLUSHDB
```

### Step 8.2: First Request - Cache Miss
```bash
curl -s http://localhost:8000/cache/reference/currencies | python3 -m json.tool
```
Look for: `"cached": false`

### Step 8.3: Second Request - Cache Hit
```bash
curl -s http://localhost:8000/cache/reference/currencies | python3 -m json.tool
```
Look for: `"cached": true`

### Step 8.4: Verify Redis Keys
```bash
redis-cli KEYS 'ml:reference:*'
```

---

## REQUIREMENT 9: CACHE INVALIDATION

### Step 9.1: Invalidate All Reference Cache
```bash
curl -X DELETE http://localhost:8000/cache/reference/all
```

### Step 9.2: Verify Cache Cleared
```bash
redis-cli KEYS 'ml:reference:*'
```

### Step 9.3: Re-fetch After Invalidation
```bash
curl -s http://localhost:8000/cache/reference/currencies | python3 -m json.tool
```
Look for: `"cached": false` (fresh load)

### Step 9.4: Add New Reference Data and Verify Refresh
```bash
# Insert a new currency (example)
mysql -h $MYSQL_HOST -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE \
  -e "INSERT INTO ref_currency (currency_code, currency_name, symbol) VALUES ('ZAR','South African Rand','R')"

# Invalidate currencies cache
curl -X DELETE http://localhost:8000/cache/reference/currencies

# Re-fetch (should miss cache and include ZAR)
curl -s http://localhost:8000/cache/reference/currencies | python3 -m json.tool
```
Look for: `"cached": false` and a record with `"code": "ZAR"` in the response.

---

## REQUIREMENT 10: PAGED GRID WITH LOOK-AHEAD CACHING

### Step 10.1: Clear Transaction Cache
```bash
redis-cli KEYS 'ml:transactions:*' | xargs redis-cli DEL
```

### Step 10.2: Request Page 1 (Triggers Look-Ahead)
```bash
curl -s "http://localhost:8000/reporting/transactions?page=1&page_size=10" | python3 -m json.tool
```
Look for: `"cached": false`, `"has_next": true`

### Step 10.3: Verify Look-Ahead Pre-cached Page 2
```bash
redis-cli KEYS 'ml:transactions:*'
```
Should show both page 1 and page 2 cached.

### Step 10.4: Request Page 2 - Cache Hit
```bash
curl -s "http://localhost:8000/reporting/transactions?page=2&page_size=10" | python3 -m json.tool
```
Look for: `"cached": true`

### Step 10.5: Request Page 1 Again - Cache Hit
```bash
curl -s "http://localhost:8000/reporting/transactions?page=1&page_size=10" | python3 -m json.tool
```
Look for: `"cached": true`

---

## REQUIREMENT 11: CACHE TELEMETRY

### Step 11.1: TTL on Reference Data (1 hour)
```bash
redis-cli TTL ml:reference:currencies
```

### Step 11.2: TTL on Transaction Pages (5 min)
```bash
redis-cli KEYS 'ml:transactions:*' | head -1 | xargs redis-cli TTL
```

### Step 11.3: Redis Memory Usage
```bash
redis-cli INFO memory | grep used_memory_human
```

### Step 11.4: Cache Hit/Miss Stats (Server Level)
```bash
redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```

---

## REQUIREMENT 12: PERSISTED CACHE METRICS (TIME-SERIES STORE)

This section demonstrates that cache metrics (hits, misses, latency, errors per minute) are persisted to Redis as a time-series store, not just tracked in-session.

### Step 12.1: Get Current Metrics Summary
```bash
curl -s http://localhost:8000/cache/metrics | python3 -m json.tool
```

Response includes:
- `current_minute`: hits, misses, errors, requests, hit_ratio for the current minute
- `totals`: all-time cumulative statistics
- `latency`: average cache vs DB latency with speedup factor
- `errors_per_minute`: current minute's error count

### Step 12.2: View Persisted Metrics Keys in Redis
```bash
redis-cli KEYS 'ml:metrics:*'
```

Expected keys:
- `ml:metrics:hits:minute:YYYYMMDDHHMM` - Minute-level hit counts
- `ml:metrics:hits:hour:YYYYMMDDHH` - Hourly hit aggregates
- `ml:metrics:hits:total` - All-time totals
- `ml:metrics:misses:*` - Same pattern for misses
- `ml:metrics:errors:*` - Same pattern for errors
- `ml:metrics:latency:cache:*` - Cache latency samples
- `ml:metrics:latency:db:*` - DB latency samples

### Step 12.3: View Hit Counts by Operation
```bash
redis-cli HGETALL 'ml:metrics:hits:total'
```

Shows hits broken down by operation type (e.g., `reference:currencies`, `transactions`).

### Step 12.4: View Miss Counts by Operation
```bash
redis-cli HGETALL 'ml:metrics:misses:total'
```

### Step 12.5: Get Hourly Metrics (Last 3 Hours)
```bash
curl -s "http://localhost:8000/cache/metrics/hourly?hours=3" | python3 -m json.tool
```

Returns hourly breakdown with:
- `hits`, `misses`, `errors`, `requests` per hour
- `hit_ratio` percentage
- `error_rate` percentage

### Step 12.6: Reset Metrics (For Testing)
```bash
curl -X DELETE http://localhost:8000/cache/metrics
```

Clears all metrics for fresh testing.

---

## GENERATE FULL LOG FILE

```bash
./generate_final_project_log.sh
```

Output file: `FINAL_PROJECT_SUBMISSION.log`

