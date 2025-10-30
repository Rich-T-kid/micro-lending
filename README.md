# Micro-Lending Platform - Technical Design Document

**Version:** 1.0  
**Authors:** Richard Baah, Jose Lamela, Saksham Mehta  
**Date:** October 30, 2025  
**GitHub:** https://github.com/Rich-T-kid/micro-lending

> See the companion **[Functional Requirements Document](Functional_Req.md)** for user-facing behavior and use cases.

---

## 1. System Architecture (High-Level Overview)

**Three-tier architecture** separating concerns:
- **Presentation Layer:** Web UI built with HTML, CSS, and JavaScript
- **Business Logic Layer:** FastAPI service exposing REST endpoints for authentication, KYC, loan applications, loans, repayments, wallets, and reports
- **Data Layer:** MySQL 8.0.42 hosted on AWS RDS at micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com with appropriate database privileges

Deployment highlights:
- Stateless API containers that scale horizontally
- AWS RDS MySQL instance with automated backups and monitoring
- Read-only analytics using the `read_only_analyst` database role

---

## 2. Technology Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python 3 with FastAPI and Pydantic for request/response validation; SQLAlchemy 2.0 with PyMySQL for database access
- **Database:** MySQL 8.0.42 on AWS RDS with schema defined in `schema.sql`
- **Authentication:** JWT-based sessions using PyJWT library; passwords hashed with SHA256
- **External Services:** Payment gateway and KYC provider integrations are simulated with metadata stored in `kyc_data` table
- **Configuration:** Environment variables managed through python-dotenv with credentials in `.env` file

---

## 3. Data Model (ER Diagram)

The complete entity-relationship diagram is available in the project documentation showing all 8 tables with their relationships and constraints.

---

## 4. Database Design Decisions

- **Normalization:** Database is designed to 3NF. Derived fields like `monthly_payment` and `outstanding_balance` are persisted for performance with the service layer maintaining consistency
- **Keys & Types:** INT AUTO_INCREMENT primary keys; DECIMAL(15,2) for monetary values; DATETIME and DATE for temporal data; BOOLEAN for flags; VARCHAR and TEXT for strings. Audit payloads are JSON-encoded as TEXT for portability
- **Referential Integrity:** Enforced with foreign keys using ON DELETE actions CASCADE, SET NULL, or RESTRICT as appropriate for each relationship
- **Constraints:** CHECK constraints enforce role/status enums, credit score ranges (300-850), non-negative balances and amounts, and interest rate bounds (0-100)
- **Indexing Strategy:** 
  - Implemented indexes: `user(email, role, created_at)`, `wallet_account(user_id, status)`, `kyc_data(user_id, verification_status)`, `loan_application(applicant_id, status, created_at)`, `loan(borrower_id, lender_id, status, maturity_date)`, `transaction_ledger(wallet_id, loan_id, transaction_type, created_at)`, `repayment_schedule(loan_id, due_date, status)`, `audit_log(user_id, (table_name,record_id), created_at)`

- **Transactions & Consistency Flows:**
  - **Disbursement:** create loan, insert loan_disbursement to ledger, update wallet balance, insert repayment schedule; all within a single transaction
  - **Repayment:** insert loan_repayment to ledger, update schedule row, update loan outstanding balance; all within a single transaction
  - **Invariant:** balance_after equals balance_before plus or minus amount, validated in service logic

---

## 5. Security Approach

- **Authentication:** JWT tokens with short expiration times using the PyJWT library
- **Password Hashing:** SHA256 hash algorithm for password storage
- **Authorization:**
  - **Application roles:** Borrower, Lender, and Admin roles enforced in middleware and controllers
  - **Database roles:** 
    - `db_admin` for full DDL and DML operations and schema management
    - `app_user` for DML operations: SELECT, INSERT, UPDATE, DELETE on application tables
    - `read_only_analyst` for SELECT only, used for reporting and analytics
- **Input Safety:** Pydantic validation combined with SQLAlchemy ORM parameterized queries and strict allow-lists for enum values
- **Secrets:** Environment variables managed through python-dotenv with database credentials stored in `.env` file
- **Auditability:** The `audit_log` table captures user actions, timestamps, IP addresses, and user agents through database triggers

---

## 6. Entitlements (Role → Functions)

- **Borrower:** create and view own applications; view KYC status; view own loans and schedules; make repayments; view own wallet and ledger
- **Lender:** view loans they fund; view repayments and portfolio summaries
- **Admin:** manage users; approve KYC; review and approve applications; disburse and cancel loans; mark defaults and paid_off status; correct ledger issues with all changes audited

**DB Execution Context:**
- API currently runs with admin credentials for development
- Analytics dashboards run as `read_only_analyst`
- Schema changes and data loads run as `db_admin`

---

## 7. Interface Design

- **Web UI** with role-aware navigation and dashboards
- **REST API Implementation:**
  - **Authentication:** `POST /auth/login`, `POST /auth/refresh`
  - **Users:** `POST /users`, `GET /users`, `GET /users/{user_id}`, `PUT /users/{user_id}`, `DELETE /users/{user_id}`
  - **KYC:** `POST /users/{user_id}/kyc`, `GET /users/{user_id}/kyc`
  - **Wallets:** `GET /users/{user_id}/accounts`, `POST /users/{user_id}/accounts`, `GET /accounts/{account_id}/transactions`
  - **Loan Applications:** `GET /users/{user_id}/loan-application`, `POST /users/{user_id}/loan-application`, `PUT /users/{user_id}/loan-applications/{application_id}`
  - **Loans:** `GET /users/{user_id}/loans`, `GET /users/{user_id}/loans/{loan_id}`, `POST /loan-offers/{offer_id}/accept`
  - **Repayments:** `GET /users/{user_id}/loans/{loan_id}/payments`, `POST /users/{user_id}/loans/{loan_id}/payments`
  - **Portfolio:** `GET /users/{user_id}/portfolio/summary`, `GET /users/{user_id}/portfolio/loans`
  - **Risk Assessment:** `GET /users/{user_id}/loan-applications/{application_id}/risk-assessment`
  - **Offers:** `GET /users/{user_id}/loan-applications/{application_id}/offers`, `POST /users/{user_id}/loan-applications/{application_id}/offers`
  - **Auto-Lending:** `GET /users/{user_id}/auto-lending/config`, `PUT /users/{user_id}/auto-lending/config`
  - **Health Check:** `GET /health`

---

## 8. Scalability Considerations

- Stateless API containers allow horizontal scaling on AWS or other cloud platforms
- AWS RDS MySQL tuned with indexing strategy on all frequently queried columns
- Read-only reporting through `read_only_analyst` role reduces load on primary database connections
- SQLAlchemy connection pooling for efficient database resource management
- API-level caching for aggregate and overdue queries
- AWS RDS automated backups and point-in-time recovery ensure data durability

---

## 9. Risks & Mitigations

- **Ledger/Balance Drift:** Multi-table updates are wrapped in database transactions with invariant enforcement and scheduled reconciliation jobs
- **Business Rule Drift:** Rules are maintained in the service layer first with database CHECK constraints and triggers added as policies stabilize
- **PII Exposure:** KYC views are restricted to Admin role with PII masked in logs and only necessary fields stored in the database

---

## 10. Testing Strategy

- **Unit Tests:** validation schemas, payment math for installments and interest split, state transitions
- **Integration Tests:** end-to-end testing of apply, approve, disburse, and repay workflows on a test database
- **Data Integrity Tests:** foreign key and CHECK constraint violations, negative balance blocking, idempotency of disbursement and repayment flows
- **Security Tests:** authorization enforcement, SQL injection attempts, password policy, audit coverage
- **Testing Framework:** pytest with test suite in `src/api_server/server_test.py`
- **Midterm Demonstration:** Test log generated via `generate_midterm_log.sh` covering all 11 database requirements

---

## 11. Deployment & Monitoring

- **Hosting:** 
  - **Database:** AWS RDS for MySQL 8.0.42 at micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com
  - **Application:** FastAPI backend deployed via AWS ECS, Railway, or similar container platforms
- **Configuration:** Environment-based database credentials via python-dotenv with credentials stored in `.env` file
- **Database Roles:**
  - Development uses `admin` credentials for full access
  - `app_user` role available for application-level DML operations
  - `read_only_analyst` role for reporting queries
- **Migrations:** Schema applied via `schema.sql` using MySQL client with DDL for all 8 tables, views, stored procedures, triggers, and roles
- **Demo Data:** Seed data included in `schema.sql` for testing with 6 users, wallets, loans, and applications
- **Monitoring:** 
  - Application logs via FastAPI
  - AWS RDS CloudWatch metrics for database performance
  - MySQL slow query log enabled for optimization
- **Backups:** AWS RDS automated daily snapshots with point-in-time recovery

---

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- MySQL 8.0+ client

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Create .env file
cat > .env << EOF
MYSQL_USER=admin
MYSQL_PASSWORD=micropass
MYSQL_HOST=micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com
MYSQL_DATABASE=microlending
JWT_SECRET=default_dev_key_replace_in_env
EOF

# 3. Initialize database
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com \
      -u admin -pmicropass microlending < db/schema.sql

# 4. Start servers (two terminals)
./start_backend.sh   # Terminal 1: API on port 8000
./start_frontend.sh  # Terminal 2: Web UI on port 3000

# 5. Access
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Demo Login: john.doe@email.com / password123
```

### Database Access

**MySQL Shell:**
```bash
./start_mysql.sh
```

**Direct Connection:**
```bash
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com \
      -u admin -pmicropass microlending
```

---

## Appendix A — Additional Enhancements

- Use MySQL JSON data type for `audit_log.old_values` and `audit_log.new_values`:
  ```sql
  ALTER TABLE audit_log
    MODIFY old_values JSON NULL,
    MODIFY new_values JSON NULL;
  ```
- Composite index for borrower's active loans:
  ```sql
  CREATE INDEX idx_loan_status_borrower ON loan (status, borrower_id);
  ```
- Application-level limit of 3 active loans per borrower validated before loan insert or update
