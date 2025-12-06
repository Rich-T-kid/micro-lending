# ETL Performance Notes

## Load Shape and Row Counts
- Typical demo load (from `FINAL_PROJECT_SUBMISSION.log`): ~400 fact rows (`fact_loan_transactions`) and 1–2 snapshot rows (`fact_daily_portfolio`); dimensions: `dim_date` ~1.1K, `dim_user` ~20, `dim_loan_product` ~8, `dim_currency` ~5, `dim_loan_status` ~8.
- Incremental runs update watermarks per table after successful extract; full runs reset watermarks to current max timestamps.

## Bulk Techniques
- Staging tables (`etl_staging_user`, `etl_staging_loan`, `etl_staging_portfolio`) are loaded in batches; users can use `LOAD DATA LOCAL INFILE` fallback to batched `executemany`.
- Fact loads run from staging via `sp_etl_load_facts_from_staging`, set-based `INSERT…SELECT` with batch guard (`p_batch_size`), and optional index disable/enable toggles in the loader.
- Session tuning for ETL (`SET foreign_key_checks=0`, `unique_checks=0`, `sql_log_bin=0`) reduces overhead during bulk operations; indexes can be re-enabled after bulk insert.

## Timings and Throughput (reference)
- Loader logs per-step durations and rows/sec; staging logs “Staged N rows via executemany/LOAD DATA INFILE in Xs”; stored procs return rows loaded/rejected and durations. Use `run_etl.py` output for current run metrics.

## Tuning Controls
- Batch size configurable (default 5,000; enforce 1K–10K) via `--batch-size` to balance memory vs round trips.
- Index rebuild toggle (`DISABLE_INDEXES_ON_BULK`) and `USE_LOAD_DATA_INFILE` flags in `reporting/etl/load.py`.
- Watermarks stored in `etl_watermarks`; adjust per-table columns if source change tracking differs.

## Data Quality Coverage
- Validation uses set-based stored proc `sp_etl_validate_staging` (nulls/ranges/FK/status enums) plus Transformer checks (null/range/FK/enum/duplicate detection). Errors flow to `etl_error_log`; counts flow to `etl_run_log` and `etl_step_log`.
