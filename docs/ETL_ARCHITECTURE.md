# ETL Architecture

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
December 2025

---

## Overview

The ETL pulls data from three different sources, cleans it up, and loads it into the star schema. We built it in Python because that's what we're comfortable with, and it has good MySQL support.

The basic flow is:
1. Extract data from the source systems
2. Run validation checks and transform the data
3. Load into the reporting database

We log everything along the way so we can debug issues and track how long things take.

---

## Source Systems

We're extracting from three logical sources (they're all in the same MySQL instance, but we treat them as separate):

**Transaction data** — This is the main operational stuff: users, loans, applications, wallet balances, payment history. This changes constantly, so we use incremental loads based on updated_at timestamps.

**Reference data** — Currency codes, loan product configurations, geographic regions, credit tier definitions. This stuff rarely changes, so we just do full refreshes. It's small enough that it doesn't matter.

**Market data** — Exchange rates, interest rate benchmarks (LIBOR, Treasury rates), credit spreads. We get daily updates and use them for currency conversion and rate benchmarking in the analytics.

---

## Extract Phase

For the initial load, we just pull everything:

```python
def extract_full(self, table, columns="*"):
    query = f"SELECT {columns} FROM {table}"
    cursor.execute(query)
    return cursor.fetchall()
```

For incremental loads, we use watermarks. The etl_watermarks table stores the last timestamp we successfully processed for each source table. Next run, we only grab records newer than that:

```python
def extract_incremental(self, table, timestamp_col, watermark):
    query = f"SELECT * FROM {table} WHERE {timestamp_col} > %s"
    cursor.execute(query, (watermark,))
    return cursor.fetchall()
```

After a successful load, we update the watermark so the next run picks up where we left off.

---

## Transform Phase

This is where we validate the data and fix it up for the reporting schema.

### Validation

We check for obvious problems before loading anything:
- Null checks on required fields (borrower_id, principal_amount, email)
- Range validation (interest rate between 0-100%, positive amounts)
- Referential integrity (does the borrower actually exist?)

The validation happens in stored procedures so we can reuse the logic:

```sql
CALL sp_etl_validate_loan(@loan_id, @borrower_id, @principal, @rate, @term, @status,
                          @is_valid OUT, @error_code OUT, @error_msg OUT);
```

If something fails, we get back an error code like INVALID_BORROWER or INVALID_RATE with a message explaining what went wrong.

### What We Do With Bad Records

Depends on the error. Invalid borrower ID? That record gets rejected and logged to the error table—we can't fix that automatically. Missing optional field? We fill in a default and keep going. Duplicate record? Update the existing one.

The etl_error_log table captures all the details: which run, which step, error code, the actual message, and the record ID so someone can investigate later.

---

## Load Phase

We don't insert directly into the fact tables. Data goes into a staging table first, gets validated, then we move the good records to the actual tables with a stored procedure:

```sql
INSERT INTO fact_loan_transactions (date_key, user_key, product_key, ...)
SELECT s.date_key, du.user_key, dp.product_key, ...
FROM etl_staging s
JOIN dim_user du ON s.borrower_id = du.user_id AND du.is_current = 1
JOIN dim_loan_product dp ON s.product_code = dp.product_code
WHERE s.is_valid = 1;
```

This handles the surrogate key lookups automatically. We join to the current version of each dimension and only insert records that passed validation.

---

## Logging

We have three tables for tracking ETL runs:

**etl_run_log** — One row per ETL execution. Captures start/end time, how many rows we processed at each stage, final status, and any error message if it failed.

**etl_step_log** — More granular. One row per step (extract users, transform loans, load facts, etc.). Useful for finding bottlenecks.

**etl_error_log** — Details on every rejected record. Error type, code, message, and the source record ID.

The Python code also writes to log files in /logs with timestamps, so we have both database records and text logs to look at.

---

## Running It

Full load (initial or reset):
```bash
python run_etl.py --mode full
```

Incremental load (daily):
```bash
python run_etl.py --mode incremental
```

The incremental mode checks watermarks and only processes new/changed records. It's what we'd run on a schedule in production.

---

## Error Scenarios

We tested a couple failure cases to make sure logging works:

**Invalid borrower** — We inserted a loan with borrower_id = 99999 (doesn't exist). The stored procedure caught it, returned INVALID_BORROWER, the record went to the error log, and the ETL continued with the other records.

**Bad interest rate** — A loan with 150% interest rate. sp_etl_validate_loan rejected it with INVALID_RATE. Same deal—logged and skipped.

The key thing is the ETL doesn't crash on bad data. It logs the problem and keeps going.
