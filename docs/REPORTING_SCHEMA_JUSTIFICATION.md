# Reporting Schema Design & Justification

## MicroLending Platform
Saksham Mehta, Jose Lamela, Richard Baah  
5th December 2025

---

## Why We Need a Separate Reporting Schema

Our OLTP database is designed for transactional workloads—inserting new loans, updating payment statuses, recording wallet transactions. It's normalized to 3NF, which is great for avoiding data anomalies and keeping writes fast. But when it comes to analytics, that normalization becomes a problem.

A typical analytics query might ask: "What was our total loan volume by product category and borrower credit tier for Q3 2025?" In the OLTP schema, answering that requires joining `loan` to `user` to `loan_application`, looking up product details from the application, parsing credit scores into tiers, and aggregating across thousands of rows. That's a lot of work, and running it against the production database would slow down the transactional operations everyone depends on.

So we built a star schema optimized for these kinds of questions. The idea is to do all the expensive joins and calculations once during ETL, then store the results in a format that's fast to query.

---

## Schema Structure

### Fact Tables

We have two fact tables that capture different views of the business:

**fact_loan_transactions** — One row per loan event (origination, payment, status change). This is the main fact table with about 400 rows in our demo data. It includes:
- Foreign keys to all dimension tables
- Numeric measures: principal amount, interest rate, outstanding balance, FX rate
- Transaction metadata: type, date

**fact_daily_portfolio** — Pre-aggregated daily snapshots of portfolio health. Instead of calculating "how many active loans do we have today?" from the transaction-level data every time, we compute it once per day and store it. Columns include:
- Date key
- Total loans, active loans, defaulted loans
- Total principal outstanding
- Default rate, average loan size

The daily portfolio table is basically a materialized aggregate. It makes dashboard queries instant because we're just reading a row instead of scanning and grouping the whole fact table.

### Dimension Tables

We have five dimensions that provide context for the facts:

**dim_date** — Calendar dimension with about 1,100 rows (covering 3 years). Standard stuff: year, quarter, month, day of week, weekend flag, fiscal period. Having this as a dimension means we can group by any time grain without date functions in the query.

**dim_user** — User dimension with SCD Type 2 for historical tracking. When a user's credit tier changes, we don't update the old row—we add a new one and mark the old one as not current. That way, loans made when a user was "Prime" stay linked to the "Prime" version of the user, even if they later got downgraded. Columns include:
- Surrogate key (user_key)
- Natural key (user_id)
- Email, role, credit tier
- SCD tracking: is_current, valid_from, valid_to

**dim_loan_product** — Loan product configurations from the reference tables. Product code, name, category, min/max amounts, base rate. About 10 products in our system.

**dim_currency** — Currency codes and symbols. Small table (8 currencies), but having it as a dimension makes currency-based grouping easy.

**dim_loan_status** — Status enumeration: active, paid_off, defaulted, cancelled. Could have been an inline field, but making it a dimension gives us flexibility to add status metadata later (like display order or color coding for dashboards).

---

## Design Decisions

### Surrogate Keys

Every dimension uses integer surrogate keys instead of the natural keys from the OLTP system. There are a few reasons for this:

1. **Consistency** — All fact-to-dimension joins use the same pattern: `fact.xxx_key = dim.xxx_key`. No guessing whether it's a UUID, a varchar code, or an integer.

2. **SCD support** — For Type 2 slowly changing dimensions, the same user_id might have multiple rows (one per historical version). The surrogate key uniquely identifies each version.

3. **Performance** — Integer comparisons are faster than string comparisons, especially for large fact tables. It also keeps the fact table rows narrower.

The downside is we need to do key lookups during ETL, but that's a one-time cost that makes every subsequent query faster.

### Partitioning

`fact_loan_transactions` is range-partitioned by date_key on quarterly boundaries:
- p_2025_q1: date_key < 20250401
- p_2025_q2: date_key < 20250701
- p_2025_q3: date_key < 20251001
- p_2025_q4: date_key < 20260101

Most analytics queries filter by date range ("show me last quarter's data"). With partitioning, MySQL can skip entire partitions that don't match the filter. A query for Q3 only scans p_2025_q3 instead of the whole table.

We chose quarterly partitions as a balance between too many partitions (monthly would give us 36 for 3 years) and too few (yearly would mean less pruning benefit). For a production system with more data, monthly might make sense.

### Indexes

We index the columns that appear in WHERE clauses and GROUP BY:

**Fact table indexes:**
- `idx_fact_loan_date` on date_key (most common filter)
- `idx_fact_loan_user` on user_key (for user-specific queries)
- `idx_fact_loan_product` on product_key (product mix analysis)
- `idx_fact_loan_status` on status_key (active vs defaulted breakdowns)

**Dimension indexes:**
- `idx_dim_date_year_month` on (year, month) for period grouping
- `idx_dim_user_current` on is_current for finding the current version
- `idx_dim_user_role_tier` on (role, credit_tier) for segmentation queries
- `idx_dim_product_category` on category for product mix queries

We try to avoid over-indexing because each index slows down the ETL load. The indexes above cover our actual query patterns.

---

## Differences from OLTP

The reporting schema is fundamentally different from the OLTP schema in several ways. The OLTP schema uses 3NF with many tables to minimize redundancy, while we use a denormalized star schema. The OLTP uses natural keys (like user IDs and currency codes), while we use surrogate integer keys for faster joins. The OLTP only stores current state, but our dimensions use SCD Type 2 to track historical changes. The workload is completely different too—OLTP handles frequent small point reads and writes, while we do batch loads and full scans with aggregations. And the indexing strategy reflects this: OLTP indexes foreign keys for lookups, while we index for filtering and grouping in analytical queries.

Essentially, the reporting schema is a read-optimized copy of the data. We trade storage space (there's some redundancy) for query speed (fewer joins, pre-computed attributes).

---

## Example Queries

Here are some typical analytics queries and why they're efficient:

### Loan Distribution by Status

```sql
SELECT s.status_name, COUNT(*) as loan_count, 
       SUM(f.principal_amount) as total_principal
FROM fact_loan_transactions f
JOIN dim_loan_status s ON f.status_key = s.status_key
WHERE f.transaction_type = 'origination'
GROUP BY s.status_name;
```

Why it's fast:
- Single join to a tiny dimension (4 rows)
- Uses idx_fact_loan_status for the status grouping
- Partition pruning if we add a date filter

### Monthly Volume Trends

```sql
SELECT d.year, d.month_name, 
       COUNT(*) as originations,
       SUM(f.principal_amount) as volume
FROM fact_loan_transactions f
JOIN dim_date d ON f.date_key = d.date_key
WHERE f.transaction_type = 'origination'
  AND d.year = 2025
GROUP BY d.year, d.month, d.month_name
ORDER BY d.month;
```

Why it's fast:
- dim_date has pre-computed year/month, no date parsing needed
- Partition pruning on 2025 quarters
- idx_dim_date_year_month supports the grouping

### Portfolio Snapshot (Instant)

```sql
SELECT date_key, total_loans, active_loans, default_rate
FROM fact_daily_portfolio
WHERE date_key >= 20251101
ORDER BY date_key;
```

Why it's fast:
- Pre-aggregated table, no joins or aggregations needed
- Just reading rows directly
- Primary key access on date_key

---

## Trade-offs

Nothing's free. Here are the costs of our approach:

**Data latency** — The reporting schema is only as fresh as the last ETL run. For our daily batch process, that means up to 24 hours of lag. Real-time dashboards would need a different approach (streaming ETL or direct OLTP queries for recent data).

**Storage** — We're storing data twice (OLTP + reporting) plus some redundancy in the denormalized dimensions. For our scale it doesn't matter, but at larger volumes we'd need to think about retention policies.

**ETL complexity** — Maintaining surrogate keys, handling SCD updates, validating data—it's more code than just querying the OLTP tables directly. But the query-time savings justify it.

**Schema changes** — If the OLTP schema changes (new column, renamed table), we need to update the ETL. There's coupling between the systems that requires coordination.

For an analytics workload with mostly historical queries and dashboard use cases, we think these trade-offs are worth it.
