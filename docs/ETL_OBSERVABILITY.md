# ETL Observability Summary

## Architecture
- Sources: OLTP (`user`, `loan`, `transaction_ledger`, etc.), reference (`ref_currency`, `ref_loan_product`, `ref_region`, `ref_credit_tier`), market (`market_fx_rates`, `market_interest_benchmarks`, `market_credit_spreads`).
- Flow: Extract (full/incremental via watermarks) → Transform (validation, enrichment with reference/market data, duplicate checks) → Stage (`etl_staging_user`, `etl_staging_loan`) → Validate (`sp_etl_validate_staging`) → Load facts from staging (`sp_etl_load_facts_from_staging`) and refresh aggregates (`sp_etl_refresh_portfolio_snapshot`).
- Control tables: `etl_run_log`, `etl_step_log`, `etl_error_log`, `etl_watermarks`.

## Data Quality Handling
- Null/range/enum/FK checks in Transformer and `sp_etl_validate_staging`.
- Duplicate detection logged via transform errors.
- Bad records are marked invalid in staging and logged to `etl_error_log`; valid rows continue (reject-and-continue pattern).

## Logging & Telemetry
- Stored procs return status/error codes; loader captures success/failure and rows loaded/rejected.
- `etl_run_log` captures run-level status, row counts, start/end times.
- `etl_step_log` captures step status, rows processed/inserted/rejected, durations, error messages.
- `etl_error_log` captures error_type/code/message, source table, record keys, timestamp.
- Structured logger (`ETLLogger`) emits INFO/WARN/ERROR with correlation IDs and writes step/error records to the database.
- Per-step metrics include rows/sec and error rates (via ETLMetrics); durations logged for each step.

## Demo Expectations
- Run `python reporting/etl/run_etl.py --mode full` then `--mode incremental` to show full and delta loads.
- Trigger validation failures (e.g., invalid borrower or rate) to populate `etl_error_log`; observe step status in `etl_step_log`.
- Query reporting tables to demonstrate efficient analytics (see `docs/REPORTING_SCHEMA_JUSTIFICATION.md` for query rationale).
