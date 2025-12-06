# ETL Architecture

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
5th December 2025

---

## Overview

This document describes the Extract-Transform-Load (ETL) pipeline that moves data from our operational systems into the reporting star schema. The ETL runs as a Python batch job that can do either full loads (for initial setup or resets) or incremental loads (for daily updates).

We chose Python for the ETL because it's what we're comfortable with, and the ecosystem has good support for both MySQL and data processing. The mysql-connector-python library handles database connections, and we didn't need anything fancier like Pandas or PySpark for our data volumes.

---

## Source Systems

We extract from three logical data sources. They're all in the same MySQL database, but we treat them as separate systems because they have different characteristics and update patterns.

### Source 1: Transaction Data (OLTP)

This is the main operational database—the tables that support day-to-day lending operations. The key tables here are `user` (borrowers and lenders), `loan` (active and historical loans), `loan_application` (submitted applications), `wallet_account` (user balances), `transaction_ledger` (all money movements), and `repayment_schedule` (payment schedules).

Most of these tables change frequently—loans get updated when payments come in, wallet balances change with every transaction. We use incremental loads based on `updated_at` timestamps. The ETL tracks watermarks and only pulls records that changed since the last successful run. The `transaction_ledger` is append-only (no updates), so we just use `created_at` as the watermark column for that one.

### Source 2: Reference Data

Static lookup tables that define the domain values and business rules. This includes `ref_currency` (currency codes like USD, EUR, GBP), `ref_loan_product` (loan product configurations with rates and limits), `ref_region` (geographic regions for borrower location), and `ref_credit_tier` (credit score tier definitions like Prime, Subprime, etc.).

This data almost never changes—maybe a new loan product once a quarter. We just do full refreshes every run. The tables are so small (maybe 5-15 rows each) that there's no performance benefit to incremental loading, and full refreshes keep the logic simple.

### Source 3: Market Data

External rate data that we use for currency conversion and rate benchmarking. The main tables are `market_fx_rates` (currency exchange rates that we get daily for each currency pair), `market_interest_benchmarks` (reference rates like SOFR and Treasury yields that update daily), and `market_credit_spreads` (credit risk spreads by tier that update weekly).

For market data, we load by date. Today's rates weren't in yesterday's run, so we pull anything with `rate_date` or `created_at` >= the last watermark.

---

## Extract Phase

The extractor pulls data from source tables and returns it as lists of dictionaries (one dict per row). It handles both full and incremental modes.

### Full Extract

For initial loads or when we want to reset everything:

```python
def extract_full(self, table, columns="*"):
    query = f"SELECT {columns} FROM {table}"
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]
```

This just pulls everything. Simple, but slow for large tables.

### Incremental Extract

For daily runs, we use watermarks to only get new/changed records:

```python
def extract_incremental(self, table, timestamp_col, watermark):
    query = f"""
        SELECT * FROM {table} 
        WHERE {timestamp_col} > %s 
        ORDER BY {timestamp_col}
    """
    cursor.execute(query, (watermark,))
    # ... same dict conversion
```

The `etl_watermarks` table tracks the last processed timestamp for each source:

```sql
SELECT source_name, table_name, column_name, watermark_value 
FROM etl_watermarks;

-- Example output:
-- oltp    | user         | updated_at | 2025-12-04 10:30:00
-- oltp    | loan         | updated_at | 2025-12-04 10:30:00
-- market  | fx_rates     | rate_date  | 2025-12-04
```

After a successful run, we update the watermark to the max timestamp we just processed. If the run fails, the watermark stays put so we re-process those records next time.

---

## Transform Phase

The transformer validates and enriches the raw data before loading. This is where we catch data quality issues and prepare records for the star schema.

### Validation Rules

We check for the common problems you'd expect in loan data. Null checks make sure required fields like `borrower_id`, `principal_amount`, and `email` actually have values. Range checks verify that numbers are within allowed bounds—interest rates should be between 0 and 100%, amounts should be positive. Enum checks make sure status values are from the allowed set (the validator looks these up from `dim_loan_status` rather than hardcoding them). FK checks verify that referenced records actually exist—we can't load a loan if the borrower doesn't exist in the user table. And duplicate checks catch repeated primary keys that would cause insert failures.

Here's an example of how we validate a loan record in the Python code:

```python
def validate_loan(self, loan):
    errors = []
    
    if loan['borrower_id'] is None:
        errors.append(('NULL_REQUIRED_FIELD', 'borrower_id is required'))
    
    if loan['principal_amount'] <= 0:
        errors.append(('OUT_OF_RANGE', 'principal must be positive'))
    
    if loan['interest_rate'] < 0 or loan['interest_rate'] > 100:
        errors.append(('OUT_OF_RANGE', 'rate must be 0-100'))
    
    if loan['status'] not in ['active', 'paid_off', 'defaulted', 'cancelled']:
        errors.append(('INVALID_STATUS', f"unknown status: {loan['status']}"))
    
    return errors
```

### Handling Bad Records

When validation fails, we don't stop the whole ETL. Instead:

1. Log the error with full details
2. Mark the record as invalid
3. Continue processing other records

This is the "reject-and-continue" pattern. The error log captures everything needed to investigate later:

```sql
INSERT INTO etl_error_log 
    (run_id, error_type, error_code, error_message, source_table, record_id)
VALUES 
    (123, 'validation', 'INVALID_BORROWER', 
     'borrower_id 99999 not found in user table', 'loan', '456');
```

For some issues, we can auto-fix:
- Trim whitespace from emails
- Default missing optional fields
- Convert duplicate inserts to updates

But for real errors (invalid FK, out-of-range values), we reject and log.

### Enrichment

We also add computed fields that the reporting schema needs:

```python
def enrich_loan(self, loan, fx_rates, credit_tiers):
    # Look up FX rate for currency conversion
    loan['fx_rate'] = fx_rates.get(loan['currency'], 1.0)
    loan['principal_usd'] = loan['principal_amount'] * loan['fx_rate']
    
    # Map credit score to tier
    score = loan['borrower_credit_score']
    for tier in credit_tiers:
        if tier['min_score'] <= score <= tier['max_score']:
            loan['credit_tier'] = tier['tier_code']
            break
    
    return loan
```

---

## Load Phase

The loader takes validated, enriched records and inserts them into the reporting schema. We use staging tables as an intermediate step.

### Staging Tables

Data goes to staging first:

```
Transformed records → etl_staging_loan → fact_loan_transactions
```

Staging tables are simpler than fact tables—no foreign keys, no triggers. This makes inserts fast. We do the key lookups and final validation in a second step.

### Surrogate Key Lookups

Facts need dimension surrogate keys, not natural keys. The loader joins staging to dimensions:

```sql
INSERT INTO fact_loan_transactions 
    (date_key, user_key, product_key, currency_key, status_key,
     loan_id, principal_amount, interest_rate, ...)
SELECT 
    d.date_key,
    u.user_key,
    p.product_key,
    c.currency_key,
    s.status_key,
    stg.loan_id,
    stg.principal_amount,
    stg.interest_rate,
    ...
FROM etl_staging_loan stg
JOIN dim_date d ON DATE(stg.created_at) = d.date_actual
JOIN dim_user u ON stg.borrower_id = u.user_id AND u.is_current = 1
JOIN dim_loan_product p ON stg.product_code = p.product_code
JOIN dim_currency c ON stg.currency = c.currency_code
JOIN dim_loan_status s ON stg.status = s.status_code
WHERE stg.is_valid = 1;
```

The `is_current = 1` filter on dim_user is important—it gets the current version of SCD Type 2 dimensions.

### Stored Procedures

We use stored procedures for the load logic so it's reusable and the validation runs in the database:

```sql
CALL sp_etl_validate_staging();  -- Mark invalid records
CALL sp_etl_load_facts_from_staging(@rows_loaded, @rows_rejected);
CALL sp_etl_refresh_portfolio_snapshot();  -- Update aggregates
```

The procedures return row counts so we can track how much data made it through.

---

## Logging

We log at three levels of detail:

### Run Level

`etl_run_log` has one row per ETL execution:

```sql
SELECT run_id, run_type, status, rows_extracted, rows_loaded, rows_rejected,
       TIMESTAMPDIFF(SECOND, started_at, completed_at) as duration_sec
FROM etl_run_log 
ORDER BY run_id DESC LIMIT 5;
```

This is the quick health check—did the last run succeed? How many rows did it process?

### Step Level

`etl_step_log` breaks it down by step:

```sql
SELECT step_name, step_type, status, rows_processed, duration_seconds
FROM etl_step_log 
WHERE run_id = 123
ORDER BY step_id;
```

If something's slow, we can see which step is the bottleneck.

### Error Level

`etl_error_log` captures every rejected record:

```sql
SELECT error_code, COUNT(*) as occurrences, error_message
FROM etl_error_log 
WHERE run_id = 123
GROUP BY error_code, error_message
ORDER BY occurrences DESC;
```

This helps diagnose data quality issues. If we suddenly have a bunch of INVALID_BORROWER errors, someone probably deleted users that had loans.

---

## Running the ETL

### Full Load

For initial setup or to reset everything:

```bash
cd reporting/etl
python run_etl.py --mode full
```

This drops existing data and reloads from scratch. Watermarks get reset to current max timestamps.

### Incremental Load

For daily runs:

```bash
python run_etl.py --mode incremental
```

This checks watermarks and only processes new/changed records since the last successful run.

### Example Output

```
[2025-12-05 10:30:15] Starting ETL run (mode=incremental)
[2025-12-05 10:30:15] Extracting from oltp.user (watermark=2025-12-04 10:30:00)
[2025-12-05 10:30:15]   Extracted 3 new/updated rows
[2025-12-05 10:30:15] Extracting from oltp.loan (watermark=2025-12-04 10:30:00)
[2025-12-05 10:30:16]   Extracted 5 new/updated rows
[2025-12-05 10:30:16] Transforming 8 records...
[2025-12-05 10:30:16]   Validated: 7 ok, 1 rejected
[2025-12-05 10:30:17] Loading to staging...
[2025-12-05 10:30:17] Executing sp_etl_load_facts_from_staging
[2025-12-05 10:30:18]   Loaded 7 rows, rejected 1
[2025-12-05 10:30:18] Updating watermarks
[2025-12-05 10:30:18] ETL completed in 3.2s
```

---

## Error Scenarios

We tested several failure cases to verify the error handling:

**Invalid foreign key** — Inserted a loan with borrower_id = 99999 (doesn't exist). The validation procedure caught it, set is_valid = 0 in staging, logged to etl_error_log with code INVALID_BORROWER, and the ETL continued with other records.

**Out-of-range value** — A loan with 150% interest rate. Rejected with INVALID_RATE. Same behavior—logged and skipped.

**Connection failure** — Killed the database mid-run. The Python code caught the exception, marked the run as failed in etl_run_log, and exited. Watermarks weren't updated, so the next run would retry.

The key principle: the ETL should never crash silently. Every failure gets logged with enough context to debug.
