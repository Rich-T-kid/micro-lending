# **Technical Design Document (TDD)**

## 1. Document Control

* **Version:** 1.0
* **Author:** Richard Baah, Jose Lamela, Saksham Mehta
* **Date:** 2025-09-04
* **Reviewers:** Development Team
* **GitHub:** https://github.com/Rich-T-kid/micro-lending

> See the companion **[Functional Requirements Document](Functional_Req.md)** for user-facing behavior and use cases.
---

## 1) System Architecture (High-Level Overview)
**Three-tier architecture** separating concerns:
- **Presentation Layer:** Web UI (HTML/CSS/JS).
- **Business Logic Layer:** FastAPI (Python 3) service exposing REST endpoints for authentication, KYC, loan applications, loans, repayments, wallets, and reports.
- **Data Layer:** **MySQL 8 (InnoDB)** hosted on Railway. The application connects using a restricted DB role (`app_user`) to enforce least privilege.

Deployment highlights:
- Stateless API containers (scales horizontally).
- Single MySQL instance for course scope (with indexes and backups).
- Read-only analytics can connect using `read_only_analyst` credentials.

---

## 2) Technology Stack
- **Frontend:** HTML, CSS, JavaScript (SPA or MPA acceptable).
- **Backend:** Python 3 + **FastAPI**; Pydantic for request/response validation; SQLAlchemy or mysqlclient/aiomysql for DB access.
- **Database:** **MySQL 8 (InnoDB)** — schema applied via `schema.sql` (provided).
- **Authentication:** JWT-based sessions; passwords hashed with **bcrypt** or **argon2** in the application layer.
- **External Services (optional stubs):** Payment rails and KYC provider integrations are simulated; metadata persists in `kyc_data` when needed.
- **Config & Secrets:** Environment variables; app uses the restricted `app_user` DB account.

---

## 3) Data Model (ER Diagram)
**[Data Model / ER Diagram](final_er_diagram.pdf)**

---

## 4) Database Design Decisions
- **Normalization:** Target **3NF**. Derived fields (`monthly_payment`, `outstanding_balance`) are persisted for performance; service layer validates and keeps them consistent.
- **Keys & Types:** INT AUTO_INCREMENT PKs; **DECIMAL(15,2)** for money; **DATETIME/DATE** for time; **BOOLEAN** flags; strings via **VARCHAR/TEXT**. Audit payloads are JSON-encoded **TEXT** (portable and easy to log).
- **Referential Integrity:** Enforced with FKs and sensible ON DELETE actions (CASCADE/SET NULL/RESTRICT) as shown in the diagram.
- **Constraints (CHECKs):** Present for role/status enums, credit score range, non-negative balances/amounts, and interest-rate bounds (0–100).
- **Indexing Strategy:** 
  - **Provided:** `user(email, role, created_at)`, `wallet_account(user_id, status)`, `kyc_data(user_id, verification_status)`, `loan_application(applicant_id, status, created_at)`, `loan(borrower_id, lender_id, status, maturity_date)`, `transaction_ledger(wallet_id, loan_id, transaction_type, created_at)`, `repayment_schedule(loan_id, due_date, status)`, `audit_log(user_id, (table_name,record_id), created_at)`.
  - **Optional additions (non-breaking):**
    - `CREATE INDEX idx_loan_status_borrower ON loan (status, borrower_id);`
    - `CREATE INDEX idx_repay_status_due ON repayment_schedule (status, due_date);`

- **Transactions & Consistency Flows:**
  - **Disbursement:** create/attach loan → insert `loan_disbursement` ledger → update wallet balance → insert schedule; **single transaction**.
  - **Repayment:** insert `loan_repayment` ledger → update schedule row → update loan outstanding; **single transaction**.
  - **Invariant:** `balance_after = balance_before ± amount` checked in service logic.

---

## 5) Security Approach
- **Authentication:** JWT tokens (short-lived). 
- **Password Hashing:** **bcrypt** (cost ≥ 12) or **argon2id**.
- **Authorization:**
  - **Application roles:** Borrower, Lender, Admin (enforced in middleware/controllers).
  - **Database roles:** 
    - `db_admin` — full DDL/DML (ops only).
    - `app_user` — DML on app tables (no DDL).
    - `read_only_analyst` — SELECT only.
- **Input Safety:** Pydantic validation + parameterized SQL/ORM; strict allow-lists for enums.
- **Secrets:** ENV vars; app never connects as `db_admin` in production.
- **Auditability:** `audit_log` captures who/when/what, IP, and user agent for sensitive actions.

---

## 6) Entitlements (Role → Functions)
- **Borrower:** create/view own applications; view KYC status; view own loans & schedules; make repayments; view own wallet/ledger.
- **Lender:** view loans they fund; view repayments and portfolio summaries.
- **Admin:** manage users; approve KYC; review/approve applications; disburse/cancel loans; mark defaults/paid_off; correct ledger issues (all changes audited).

**DB Execution Context:**
- API runs as `app_user` (least privilege).
- Analytics dashboards run as `read_only_analyst`.
- Schema changes and data loads run as `db_admin`.

---

## 7) Interface Design
- **Web UI** with role-aware navigation and dashboards.
- **Representative REST API** (non-exhaustive):
  - `POST /auth/login`, `POST /users`, `GET /users/me`
  - `GET/POST /kyc`, `PATCH /kyc/{id}`
  - `POST /applications`, `GET /applications?status=...`, `PATCH /applications/{id}`
  - `POST /loans` (from approved applications), `GET /loans?status=...`, `PATCH /loans/{id}`
  - `GET /loans/{id}/schedule`, `POST /loans/{id}/repay`
  - `GET /wallets/{userId}`, `GET /wallets/{id}/ledger`
  - `GET /reports/overdue`, `GET /reports/portfolio`, `GET /reports/cashflow`

---

## 8) Scalability Considerations
- Stateless API containers allow horizontal scaling on AWS.
- MySQL tuned via pragmatic indexing; read-only reporting through `read_only_analyst` reductions.
- Optional API-level caching for aggregate/overdue queries.
- Backups and restore runbooks ensure recoverability.

---

## 9) Risks & Mitigations
- **Ledger/Balance Drift:** Wrap multi-table updates in DB transactions; enforce invariants; schedule reconciliation jobs.
- **Business Rule Drift:** Keep rules in service layer first; add DB CHECKs/triggers when policy stabilizes (avoids churn).
- **PII Exposure (KYC):** Restrict KYC views to Admin; mask PII in logs; avoid exporting raw documents; store only necessary fields.

---

## 10) Testing Strategy
- **Unit Tests:** validation schemas; payment math (installments, interest split); state transitions.
- **Integration Tests:** end-to-end apply→approve→disburse→repay on a test DB.
- **Data Integrity Tests:** FK/CHECK violations; negative balances blocked; idempotency of disbursement and repayment flows.
- **Security Tests:** authZ enforcement; injection attempts; password policy; audit coverage.

---

## 11) Deployment & Monitoring
- **Hosting:** AWS ECS (Fargate) container + Amazon RDS for MySQL.
- **Configuration:** ENV-based DB credentials; app uses `app_user` in prod.
- **Migrations:** Apply provided `schema.sql`; seed demo data for classroom testing.
- **Monitoring:** App/DB logs; slow query log; alerting is minimal but sufficient for course scope.
- **Backups:** Daily snapshots; verified restore process for demonstrations.

---

## Appendix A — Optional, Non-Breaking Enhancements
- Use MySQL `JSON` for `audit_log.old_values/new_values`:
  ```sql
  ALTER TABLE audit_log
    MODIFY old_values JSON NULL,
    MODIFY new_values JSON NULL;
  ```
- Composite index for borrower’s active loans:
  ```sql
  CREATE INDEX idx_loan_status_borrower ON loan (status, borrower_id);
  ```
- App-level guardrail: “≤ 3 active loans per borrower” validated before `loan` insert/update.
