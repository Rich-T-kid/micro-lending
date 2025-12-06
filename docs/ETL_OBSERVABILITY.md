# ETL Observability & Logging Design

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
5th December 2025

---

## Introduction

This document covers how we handle logging, error tracking, and telemetry in our ETL pipeline. The goal was to build something that lets us see what's happening during a run, figure out why something failed, and get enough metrics to know if the system is healthy.

We ended up with a mix of database tables for structured logs and Python logging for real-time output. It's not fancy, but it works and gives us what we need for debugging and monitoring.

---

## ETL Architecture Overview

Before getting into the logging, here's the quick version of how data flows through our system.

### Data Sources

We pull from three logical sources (all in the same MySQL database, but we treat them separately):

1. **Transaction Data (OLTP)** — The core operational tables: `user`, `loan`, `loan_application`, `wallet_account`, `transaction_ledger`, `repayment_schedule`. This is where most of the activity happens, so we use incremental loads based on timestamps.

2. **Reference Data** — Static lookup tables: `ref_currency`, `ref_loan_product`, `ref_region`, `ref_credit_tier`. These rarely change, so we just do full refreshes each time. The tables are small enough that it doesn't matter.

3. **Market Data** — External rates and benchmarks: `market_fx_rates`, `market_interest_benchmarks`, `market_credit_spreads`. We get daily updates and use them for currency conversion and rate comparisons in the analytics.

### Data Flow

The pipeline runs in four stages:

1. **Extract** — Pull data from all three sources. For transaction data, we use watermarks to get only new/changed records. Reference and market data are small enough that we just grab everything.

2. **Transform** — Validate each record (null checks, range checks, FK validation) and enrich it by joining to reference data for lookups and market data for FX rates.

3. **Stage** — Load the validated records into staging tables (`etl_staging_user`, `etl_staging_loan`). These are simpler than the final tables—no FK constraints—so inserts are fast.

4. **Load** — Move data from staging into the star schema. Dimensions get upserted (SCD Type 2 for users), facts get appended. We use stored procedures to handle the surrogate key lookups and final validation.

---

## Data Quality Rules

We validate data at two points: in Python during the transform phase, and again in MySQL stored procedures before loading. The redundancy is intentional—we want to catch problems early, but also have a safety net in case something slips through.

### Validation Checks

We run several types of validation on incoming data:

**Null checks** make sure required fields actually have values—things like `borrower_id`, `principal_amount`, and `email` can't be empty. **Range validation** verifies numeric values are within reasonable bounds (interest rates should be 0-100%, amounts should be positive). **Enum validation** confirms status values match the allowed set—a loan status has to be one of active, paid_off, defaulted, or cancelled, not some random string. **Referential integrity checks** verify that foreign keys point to real records—we can't have a transaction referencing a borrower that doesn't exist. And **duplicate detection** catches repeated records, like the same loan_id with the same transaction_type on the same date.

### How We Handle Bad Records

This is the "reject-and-continue" pattern. When we find a bad record, we don't stop the whole ETL. Instead:

1. **Mark it invalid** in the staging table (`is_valid = 0`)
2. **Log the error** with details about what went wrong
3. **Keep processing** the rest of the batch

The stored procedure `sp_etl_validate_staging` handles the database-side checks. It returns error codes like `INVALID_BORROWER` or `INVALID_RATE` along with a human-readable message. The Python code catches these and writes them to the error log.

For some issues, we can fix them automatically:
- Missing optional fields get default values
- Duplicate records trigger an UPDATE instead of INSERT
- Whitespace in emails gets trimmed

But for real errors (invalid foreign keys, out-of-range values), we reject the record and move on. Someone can look at the error log later and decide what to do.

---

## Logging Model

We log to two places: database tables for structured data we want to query, and Python log files for real-time debugging.

### Database Logging Tables

**etl_run_log** — One row per ETL execution
```sql
CREATE TABLE etl_run_log (
    run_id INT AUTO_INCREMENT PRIMARY KEY,
    run_type ENUM('full', 'incremental'),
    status ENUM('running', 'completed', 'failed'),
    rows_extracted INT,
    rows_transformed INT,
    rows_loaded INT,
    rows_rejected INT,
    started_at DATETIME,
    completed_at DATETIME,
    error_message TEXT
);
```

This gives us a high-level view of each run. We can quickly see if the last run succeeded, how many rows it processed, and how long it took.

**etl_step_log** — One row per step within a run
```sql
CREATE TABLE etl_step_log (
    step_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT,
    step_name VARCHAR(100),
    step_type ENUM('extract', 'transform', 'load'),
    status ENUM('running', 'completed', 'failed'),
    rows_processed INT,
    rows_inserted INT,
    rows_rejected INT,
    duration_seconds DECIMAL(10,2),
    error_message TEXT
);
```

More granular than the run log. If a run fails, we can look here to see exactly which step had the problem. We also track duration per step so we can find bottlenecks.

**etl_error_log** — One row per rejected record
```sql
CREATE TABLE etl_error_log (
    error_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT,
    step_id INT,
    error_type VARCHAR(50),
    error_code VARCHAR(50),
    error_message TEXT,
    source_table VARCHAR(100),
    record_id VARCHAR(100),
    created_at DATETIME
);
```

The most detailed log. Every rejected record gets a row here with the error type, code, message, and which source record caused the problem. This is what we'd use to investigate specific failures.

### Python Logging

We use Python's logging module with a custom formatter that includes timestamps and correlation IDs:

```python
import logging

class ETLLogger:
    def __init__(self, run_id):
        self.run_id = run_id
        self.logger = logging.getLogger('etl')
        
    def info(self, message):
        self.logger.info(f"[run={self.run_id}] {message}")
        
    def error(self, message, error_code=None):
        self.logger.error(f"[run={self.run_id}] [{error_code}] {message}")
```

Log files go to `/logs/etl_YYYYMMDD.log`. We keep 7 days of logs before rotating them out.

---

## Telemetry Strategy

### What We Track

For each ETL run:
- **Row counts**: extracted, transformed, loaded, rejected at each stage
- **Timing**: duration per step, total run time, rows per second
- **Error rates**: percentage of records rejected, error codes by frequency

### Metrics Collection

The `ETLMetrics` class collects stats during a run:

```python
class ETLMetrics:
    def __init__(self):
        self.step_timings = {}
        self.row_counts = {}
        
    def record_step(self, step_name, rows, duration):
        self.step_timings[step_name] = duration
        self.row_counts[step_name] = rows
        rate = rows / duration if duration > 0 else 0
        print(f"{step_name}: {rows} rows in {duration:.2f}s ({rate:.0f} rows/sec)")
```

At the end of each run, we write a summary to the log showing all the metrics. This helps us spot trends—if the transform step is getting slower over time, we know to investigate.

### How This Would Work in Production

In a real deployment, we'd probably:

1. **Push metrics to Prometheus or CloudWatch** instead of just logging them. That way we can set up alerts if error rates spike or runs take too long.

2. **Build a dashboard** showing ETL health over time: run success rate, average duration, records processed per day.

3. **Set up alerting** for failed runs or high rejection rates. Right now we'd have to check the logs manually.

For this project, we kept it simple with database tables and log files. But the structure is there to plug into a real monitoring system.

---

## Error Recovery

When something goes wrong, here's how we handle it:

**Transient failures** (network timeout, deadlock) — We retry up to 3 times with exponential backoff. Most transient issues clear up on their own.

**Data validation failures** — Log to error table, skip the record, continue processing. The error log has enough detail to fix the source data and re-run.

**Fatal errors** (can't connect to database, missing source table) — Log the error, mark the run as failed, exit. No point continuing if we can't access what we need.

The watermarks only update after a successful run, so if something fails partway through, the next run will re-process from where the last successful run ended. We might get some duplicate processing, but it's better than missing data.

---

## Demo Queries

To check on ETL health, we run queries like:

```sql
-- Last 5 ETL runs
SELECT run_id, run_type, status, rows_loaded, rows_rejected,
       TIMESTAMPDIFF(SECOND, started_at, completed_at) as duration_sec
FROM etl_run_log 
ORDER BY run_id DESC LIMIT 5;

-- Error breakdown for a specific run
SELECT error_code, COUNT(*) as occurrences
FROM etl_error_log
WHERE run_id = 123
GROUP BY error_code;

-- Slowest steps across recent runs
SELECT step_name, AVG(duration_seconds) as avg_duration
FROM etl_step_log
WHERE run_id IN (SELECT run_id FROM etl_run_log ORDER BY run_id DESC LIMIT 10)
GROUP BY step_name
ORDER BY avg_duration DESC;
```

These give us a quick picture of whether things are working and where to look if they're not.
