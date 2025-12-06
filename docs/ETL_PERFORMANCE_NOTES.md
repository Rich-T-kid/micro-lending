# ETL Performance Notes

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
December 2025

---

## Overview

This document covers the performance characteristics of our ETL pipeline and the techniques we use to keep it running efficiently. Most of the optimizations are standard bulk loading practices, but we'll explain why we chose each approach.

---

## Data Volumes

For our demo, the data volumes are small:
- **Users:** ~20 records
- **Loans:** ~30 records  
- **Transactions:** ~400 fact rows after transformation
- **Daily snapshots:** 1-2 rows per day
- **Dimensions:** dim_date has ~1,100 rows (3 years), others are under 20 rows each

At this scale, performance optimizations don't really matter—the whole ETL finishes in a few seconds either way. But we implemented the techniques anyway because they'd matter at production scale, and it was a good learning exercise.

---

## Bulk Loading Techniques

### Staging Tables

We never insert directly into the fact tables. Data goes through staging first:

```
Source → Extract → Staging Table → Validate → Fact Table
```

The staging tables (`etl_staging_user`, `etl_staging_loan`, `etl_staging_portfolio`) are simpler than the final tables—no foreign key constraints, no triggers. This means inserts are fast. We do all the validation and key lookups in a second step before moving data to the real tables.

### Batch Inserts

Instead of inserting one row at a time, we batch them up:

```python
# Bad - one round trip per row
for row in data:
    cursor.execute("INSERT INTO staging ...", row)

# Good - one round trip for many rows
cursor.executemany("INSERT INTO staging ...", data)
```

The `executemany` approach is way faster because it reduces network round trips. We use a batch size of 5,000 rows by default, which balances memory usage against the number of database calls.

### Session Tuning

During bulk loads, we temporarily disable some MySQL checks:

```sql
SET foreign_key_checks = 0;
SET unique_checks = 0;
SET sql_log_bin = 0;
```

This speeds up inserts because MySQL doesn't have to verify constraints or write to the binary log for each row. We re-enable them after the load completes. Obviously, this only makes sense for batch loading where we've already validated the data in Python.

### LOAD DATA INFILE

For really large datasets, we have the option to use MySQL's `LOAD DATA LOCAL INFILE`, which is faster than regular INSERTs:

```python
# Write data to temp file
with open('/tmp/staging.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerows(data)

# Bulk load from file
cursor.execute("""
    LOAD DATA LOCAL INFILE '/tmp/staging.csv'
    INTO TABLE etl_staging_loan
    FIELDS TERMINATED BY ','
""")
```

We don't use this by default because `executemany` is fast enough for our data volumes and doesn't require file I/O. But the code is there if we need it.

---

## Incremental Loading

Full loads are simple but slow—you're reprocessing everything every time. Incremental loads only process new and changed records, which is much more efficient for daily runs.

### Watermarks

We track the "high water mark" for each source table:

```sql
SELECT watermark_value FROM etl_watermarks 
WHERE source_name = 'oltp' AND table_name = 'loan';
-- Returns: 2025-12-04 10:30:00
```

The next incremental load only pulls records where `updated_at > '2025-12-04 10:30:00'`. After a successful load, we update the watermark to the max timestamp we just processed.

If a run fails, we don't update the watermark. That means the next run will re-try the same records, which might cause some duplicate processing but ensures we don't miss data.

### Change Detection

For tables that don't have an `updated_at` column, we use other approaches:
- **Reference data:** Just do a full refresh. The tables are tiny.
- **Market data:** Load by date. Today's rates weren't there yesterday.
- **Transaction ledger:** Append-only, so we use `created_at` as the watermark.

---

## Timing Measurements

The ETL logs duration for each step so we can identify bottlenecks:

```
[2025-12-05 10:30:15] extract_users: 20 rows in 0.12s (167 rows/sec)
[2025-12-05 10:30:15] extract_loans: 27 rows in 0.08s (338 rows/sec)
[2025-12-05 10:30:16] transform_all: 47 rows in 0.45s (104 rows/sec)
[2025-12-05 10:30:17] load_facts: 400 rows in 0.89s (449 rows/sec)
[2025-12-05 10:30:17] Total: 1.54s
```

The transform step is usually the slowest because it does validation and enrichment. The load step is fast because we're using batch inserts into staging tables.

We also store timing in `etl_step_log` so we can track trends over time:

```sql
SELECT step_name, AVG(duration_seconds) as avg_sec
FROM etl_step_log
GROUP BY step_name
ORDER BY avg_sec DESC;
```

---

## Index Management

For large loads, it can be faster to disable indexes, load the data, and rebuild indexes afterward. This is because MySQL doesn't have to update the index for every row inserted—it builds the whole thing once at the end.

```python
# Optional - only worth it for big loads
if DISABLE_INDEXES_ON_BULK:
    cursor.execute("ALTER TABLE fact_loan_transactions DISABLE KEYS")
    
# ... do the bulk insert ...

if DISABLE_INDEXES_ON_BULK:
    cursor.execute("ALTER TABLE fact_loan_transactions ENABLE KEYS")
```

We don't enable this by default because our loads are small enough that it doesn't matter. But for initial loads with millions of rows, it would help.

---

## Configuration Options

The loader has a few knobs for tuning. The `batch_size` setting controls how many rows we insert per batch (defaults to 5000). `USE_LOAD_DATA_INFILE` switches to file-based loading instead of multi-row inserts (defaults to False since it requires special MySQL permissions). And `DISABLE_INDEXES_ON_BULK` will drop indexes before loading and rebuild them after (also defaults to False, since our loads are small enough that it doesn't make a difference).

These can be adjusted via command-line flags:

```bash
python run_etl.py --mode full --batch-size 10000
```

---

## What We'd Do Differently at Scale

If we were handling millions of records instead of hundreds:

1. **Parallel extraction** — Pull from multiple source tables simultaneously using threading or async.

2. **Partitioned loading** — Load into date-partitioned staging tables, then exchange partitions into the fact table. Avoids blocking reads during loads.

3. **Streaming transforms** — Instead of loading everything into memory, process in chunks. Our current approach loads all extracted data into Python lists, which won't work for huge datasets.

4. **Connection pooling** — Reuse database connections instead of opening new ones. Saves connection overhead.

5. **Monitoring** — Push metrics to a time-series database (Prometheus, InfluxDB) and set up alerts for slow runs or high error rates.

For a class project, none of this was necessary. But it's good to think about what would need to change.
