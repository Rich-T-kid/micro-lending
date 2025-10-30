
# **Functional Requirements Document (FRD)**

* **Version:** 1.0
* **Author:** Richard Baah, Jose Lamela, Saksham Mehta
* **Date:** 2025-09-14
* **Reviewers:** Development Team, Product Owner, Stakeholders

## Project Overview
The Microlending Platform stores data for: users and KYC records, per‑user wallet accounts, loan applications and loans, a repayment schedule, an append‑only transaction ledger tied to **one wallet** (and optionally a loan), and an audit log of key changes. The schema also includes DB roles, views for reporting, triggers for validation/audit, and stored procedures for common workflows.

## User Roles (as stored in the schema)
- **Application roles (user.role)**: `borrower`, `lender`, `admin` (CHECK enforced).  
- **Database roles**: `db_admin`, `app_user`, `read_only_analyst` with privileges granted per table.

## Core Functionality (backed by schema structures)
1. **Users & KYC**
   - `user` table with unique email, hashed password, credit score bounds, and role domain constraint.
   - `kyc_data` rows linked to a `user` via `user_id` (required) and optional `verified_by` (FK set NULL on delete). Status domain via CHECK.
2. **Wallets & Ledger**
   - `wallet_account` linked to a `user` (required). Balance has non‑negative CHECK; status domain via CHECK.
   - Transaction types constrained by CHECK. Records include `amount`, `balance_before`, `balance_after`, `reference_number` (UNIQUE), and `created_at`.
3. **Loan Applications & Loans**
   - `loan_application` linked to applicant (`user`) and optional reviewer (`user`). Amount/term/rate validated via CHECK; status via CHECK.
   - `loan` optionally linked to the originating application; references borrower (required) and lender (optional). Principal/term/rate bounds and `outstanding_balance >= 0` via CHECK; status domain via CHECK.
4. **Repayment Schedule**
   - `repayment_schedule` per `loan` with installment number, due date, amounts (all non‑negative CHECKs), status domain via CHECK.
5. **Audit**
   - `audit_log` captures `user_id` (optional), `action`, `table_name`, `record_id`, `old_values`, `new_values`, timestamps, and client hints. Triggers write to this table on relevant events.

## Business Rules (only those enforced by the schema)
- **Domains (CHECK):**
  - `user.role ∈ {borrower,lender,admin}`; `user.credit_score ∈ [300,850]`.
  - `wallet_account.balance ≥ 0`; `wallet_account.status ∈ {active,frozen,closed}`.
  - `loan_application.amount > 0`, `term_months > 0`, `0 ≤ interest_rate ≤ 100`; status in `{pending,approved,rejected,withdrawn}`.
  - `loan.principal_amount > 0`, `term_months > 0`, `0 ≤ interest_rate ≤ 100`, `outstanding_balance ≥ 0`; status in `{active,paid_off,defaulted,cancelled}`.
  - `repayment_schedule` amounts ≥ 0; status in `{pending,paid,overdue,partial}`.
  - `transaction_ledger.transaction_type ∈ {deposit,withdrawal,loan_disbursement,loan_repayment,fee,interest,transfer}`.
- **Referential Integrity (FKs):** as declared between `user`, `wallet_account`, `kyc_data`, `loan_application`, `loan`, `repayment_schedule`, `transaction_ledger`, `audit_log` with `CASCADE/SET NULL/RESTRICT` per table.
- **Triggers:** email/role normalization & validation on `user` insert; audit entries on `user` insert, `loan` update, `wallet_account` update.
- **Views:** `v_active_loans`, `v_portfolio_dashboard`, `v_user_profile_safe` define reporting interfaces built from base tables.

## Use Cases (as supported by schema objects)
1. **Create user; insert KYC rows** — triggers validate/normalize and audit inserts.
2. **Submit loan application** — validated by CHECKs; reviewer linkage optional.
3. **Create loan from application** — FKs connect borrower, lender, and application.
4. **Record disbursement/repayment** — insert into `transaction_ledger` with optional `loan_id`; update balances and related rows via application logic or stored procedure.
5. **Track repayment schedule** — due amounts and statuses stored per installment; queries supported by indexes.
6. **Reporting & audit** — use provided views and `audit_log` to review activity.

## Non‑Functional Requirements (schema‑related)
- **Performance:** Indexes exist on common filters/joins (email, role, created_at, user_id, status, due_date, loan_id, etc.).
- **Security / Access:** DB roles and grants codified; audit trail recorded by triggers.
- **Integrity:** CHECKs & FKs enforce domains and relationships; `created_at` stamps; normalization to 3NF with a few persisted summary fields (`monthly_payment`, `outstanding_balance`).