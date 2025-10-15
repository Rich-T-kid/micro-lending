# Microlending Database (Basics)

A small, focused repo for the **database** behind a microlending app. It contains SQL to create the schema, seed minimal reference data, and add helpful indexes/views. The DB runs on **Amazon RDS for MySQL** so teammates can connect and work from anywhere (with access allowed).

---

## What This Does

* **Creates tables & relations** for users, roles, loan applications, risk, offers, loans, repayments, transactions, messages, and audit.
* **Seeds** baseline data (roles, currencies).
* **Adds indexes & views** to speed up common queries (offers per application, overdue installments, cash flows, latest message per thread).

> Default DB charset/collation targets full Unicode on MySQL 8: `utf8mb4` + `utf8mb4_0900_ai_ci`.

---

## Connect to the Database (RDS)

**You need:** the RDS **endpoint**, **port** (3306), **database name** (e.g., `microlending`), and a **username/password**. Your IPv4 address must be allowed in the RDS **Security Group** (Inbound: MySQL/Aurora 3306 from `your.ip.addr.ess/32`).

### CLI (mysql)

```bash
# Optionally load .env if you have these set
set -a; source .env; set +a

mysql -h "$MYSQL_HOST" -P 3306 -u "$MYSQL_USER" -p
```

### Workbench / DBeaver

* **Hostname:** `<rds-endpoint>`
* **Port:** `3306`
* **Username:** `<username>`
* **Password:** `<password>`
* **Database:** `microlending`

---

## Create DB & Run Migrations (once per environment)

If the `microlending` database does not exist yet:

```bash
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <admin-or-migration-user> -p \
  -e "CREATE DATABASE IF NOT EXISTS microlending CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
```

Apply migrations in order (from the repo root):

```bash
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0001_init.sql
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0002_seed_minimum.sql
mysql --ssl-mode=REQUIRED -h <endpoint> -P 3306 -u <user> -p microlending < db/migrations/0003_indexes.sql
```

---

## Environment Variables (optional, for convenience)

Create a local `.env` (do **not** commit real secrets):

```dotenv
MYSQL_HOST=your-db-endpoint.rds.amazonaws.com
MYSQL_PORT=3306
MYSQL_DATABASE=microlending
MYSQL_USER=app_user
MYSQL_PASSWORD=replace-me
```

Load them before running CLI commands:

```bash
set -a; source .env; set +a
```

---

## Quick Security Notes

* **Allow-list IPv4 only** (Inbound 3306 from `x.x.x.x/32`). Avoid `0.0.0.0/0`.
* Use a **least-privilege user** for app and teammate access; keep the admin user for migrations.
* Keep **SSL enabled** (`--ssl-mode=REQUIRED`).

---

## Repo Layout

```
 db/
 ├─ migrations/
 │  ├─ 0001_init.sql
 │  ├─ 0002_seed_minimum.sql
 │  └─ 0003_indexes.sql
 └─ scripts/
    └─ migrate.sh (optional helper)
```

That’s it. Share your endpoint and a user with teammates (and allow their IPs) so they can connect and start inserting/querying.
