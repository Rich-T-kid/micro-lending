# Reporting Schema Justification

## Pattern Choice and Fit for Analytics
We use a star schema with two fact tables (`fact_loan_transactions`, `fact_daily_portfolio`) and five dimensions (`dim_date`, `dim_user`, `dim_loan_product`, `dim_currency`, `dim_loan_status`). The OLTP schema is highly normalized (3NF across `user`, `loan`, `transaction_ledger`, `repayment_schedule`), optimized for point writes and strict constraints. For BI, we need stable, denormalized keys, predictable join paths, and time-based partitioning; the star keeps query plans simple, reduces join depth, and allows parallel bulk loads independent of the transactional workload.

## Differences vs OLTP and Why It Matters
- **Keys and Surrogates:** OLTP uses natural ints per table; reporting dimensions use surrogate keys and SCD flags (e.g., `dim_user.is_current`) to freeze historical attributes. Facts store dimension keys, not the full OLTP payload, avoiding late-binding lookups at query time.
- **Denormalization:** Product, currency, and status attributes are pre-flattened into dimensions. This eliminates cross-table joins for common dashboards (status, product mix, currency).
- **Partitioning/Clustering:** `fact_loan_transactions` is range-partitioned by `date_key` (quarterly), aligning with the dominant time filters; this prunes partitions for month/quarter queries. Secondary indexes support user/product/status filters.
- **Workload Isolation:** Reporting tables are append-only and loaded in batches from staging; no OLTP triggers or transactional constraints run during analytics loads, keeping BI read patterns off the write-optimized OLTP tables.

## Performance Optimizations
- **Partitioning:** RANGE on `date_key` (quarters) in `fact_loan_transactions` cuts scan volume for date-sliced queries.
- **Indexing:** Facts index `user_key`, `product_key`, `status_key`, `transaction_type`, `loan_id`; dimensions index natural keys and common filters (`dim_date` year/month/quarter, `dim_user` role/tier/current, `dim_loan_product` category/current).
- **Narrow Fact Rows:** Facts carry numeric metrics (principal, interest, fx_rate, balances) and keys only; text blobs stay in dimensions.
- **Staging + Bulk Load:** Loads run via staging tables and stored procs; indexes can be disabled during bulk insert and rebuilt after (see loader config).

## Example Analytical Queries and Efficiency
1) **Loan distribution by status**  
   Uses `fact_loan_transactions` joined to `dim_loan_status`; hits `idx_fact_loan_status` and small dimension. Partition pruning by `date_key` if filtered.
2) **Portfolio volume by month**  
   Groups by `dim_date` month/ year; `dim_date` supplies calendar attributes without recalculating; partition pruning on fact date; `idx_dim_date_year_month` supports grouping.
3) **Daily portfolio snapshot**  
   Reads `fact_daily_portfolio` directly—pre-aggregated, unique per `date_key` with `uk_portfolio_date` so no fact scan is required for daily KPIs.

These queries require only one small-dimension join (or none), use integer surrogate keys, benefit from partition pruning on `date_key`, and rely on precomputed aggregates where available.
