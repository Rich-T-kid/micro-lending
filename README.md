# Micro-Lending Platform

A comprehensive micro-lending platform supporting borrowers, lenders, and administrative operations. Includes a MySQL database schema, FastAPI backend, and admin/reporting endpoints.

---

## Project Overview

This project provides:
- **Database schema** for users, loans, repayments, transactions, ratings, and admin features
- **FastAPI backend** for authentication, user management, KYC, wallet, loan applications, risk assessment, offers, payments, portfolio, auto-lending, ratings, admin, and reporting
- **Admin dashboard** and compliance endpoints

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- MySQL 8+ (Amazon RDS recommended)
- Docker (optional, for local MySQL)

### Clone the Repository
```bash
git clone https://github.com/Rich-T-kid/micro-lending.git
cd micro-lending
```

### Install Python Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Database Setup
1. Create a MySQL database (see below for charset/collation)
2. Apply migrations:
```bash
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0001_init.sql
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0002_seed_minimum.sql
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0003_indexes.sql
```
Or use the helper script:
```bash
sh db/scripts/migrate.sh
```

### Environment Variables
Create a `.env` file with your database credentials:
```dotenv
MYSQL_HOST=your-db-endpoint.rds.amazonaws.com
MYSQL_PORT=3306
MYSQL_DATABASE=microlending
MYSQL_USER=app_user
MYSQL_PASSWORD=replace-me
```

---

## How to Run the API Server

1. Activate your Python environment:
```bash
source .venv/bin/activate
```
2. Start the FastAPI server:
```bash
python src/api_server/server.py
```
Or with Uvicorn:
```bash
uvicorn src/api_server/server:app --reload
```
3. Visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive Swagger UI.

---

## Current Implementation Status

- **Database:**
  - Schema, migrations, and seed data complete
  - Indexes and views for performance
- **API Server:**
  - All major endpoints implemented (auth, users, KYC, wallet, loans, offers, payments, ratings, admin, reporting)
  - JWT authentication and error handling
  - Admin dashboard, compliance, and reporting endpoints
  - Ratings & review system simplified and functional
- **Testing:**
  - Pytest configuration included
  - Unit and integration tests in `src/api_server/server_test.py`
- **Docs:**
  - Swagger/OpenAPI spec in `src/api_server/spec.yml`
  - Architectural and technical docs in repo root

---

## Repo Layout

```
├── db/
│   ├── migrations/
│   └── scripts/
├── src/api_server/
│   ├── models.py
│   ├── server.py
│   ├── server_test.py
│   └── spec.yml
├── requirements.txt
├── README.md
└── ...
```

---

## Notes
- Default DB charset/collation: `utf8mb4` + `utf8mb4_0900_ai_ci`
- Use SSL for all database connections
- Allow-list only trusted IPs for RDS
- For questions, see `Technical_Design_Doc.md` or contact repo owner
