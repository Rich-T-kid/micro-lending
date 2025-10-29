# Micro-Lending Platform

Database Administration Course - Midterm Project

A full-stack micro-lending platform demonstrating core database administration concepts. Borrowers apply for loans, lenders fund applications, and admins manage the platform.

## Architecture

```
Frontend (Express:3000) → Backend (FastAPI:8000) → Database (MySQL 8.0 RDS)
```

- **Frontend**: HTML/CSS/JS with Express.js, JWT auth in localStorage
- **Backend**: FastAPI REST API with SQLAlchemy ORM, SHA256 password hashing  
- **Database**: MySQL 8.0 on AWS RDS - 8 core tables with constraints/indexes

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 16+
- MySQL 8.0+ access

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
JWT_SECRET=your_secret_key_here
EOF

# 3. Initialize database
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com \
      -u admin -pmicropass microlending < db/schema.sql

# 4. Start servers (two terminals)
./start_backend.sh   # Terminal 1
./start_frontend.sh  # Terminal 2

# 5. Access
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Login: john.doe@email.com / password123
```

### Database Access

**MySQL Shell (Mac/Linux):**
```bash
./start_mysql.sh
```

**Direct Connection:**
```bash
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com \
      -u admin -pmicropass microlending
```

**Windows Users:**
- Install MySQL Workbench: https://dev.mysql.com/downloads/workbench/
- Connection details from `.env` file (host, user, password, database)

**Mac Setup:**
```bash
brew install mysql-client
echo 'export PATH="/opt/homebrew/opt/mysql-client/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Project Structure

```
microlending_project/
├── db/
│   ├── schema.sql              # Complete schema + demo data
│   └── reset.sql               # Drop tables
├── src/api_server/
│   ├── server.py              # FastAPI app with all endpoints
│   ├── models.py              # SQLAlchemy ORM
│   └── server_test.py         # Tests
├── frontend/
│   ├── *.html                 # Pages
│   ├── js/api.js              # API client with JWT
│   └── server.js              # Express server
├── midterm_complete.py         # Midterm demo script
├── MIDTERM_SUBMISSION.log      # Demo output
└── requirements.txt            # Python deps
```

## Database Schema

### 8 Core Tables

1. `user` - User accounts (borrowers, lenders, admins)
2. `wallet_account` - Financial balances
3. `kyc_data` - Identity verification
4. `loan_application` - Loan requests from borrowers
5. `loan` - Active and completed loans
6. `transaction_ledger` - All financial transactions
7. `repayment_schedule` - Payment tracking
8. `audit_log` - Activity audit trail

### Key Features
- PRIMARY KEY with AUTO_INCREMENT on all tables
- FOREIGN KEY relationships with CASCADE/RESTRICT/SET NULL
- CHECK constraints (credit scores 300-850, positive amounts)
- UNIQUE constraints on emails, account numbers
- 25+ indexes for query performance

## Authentication

**Password Hashing**: SHA256 via \`hashlib.sha256\` (backend requirement, not bcrypt)

**Demo Users** (password: \`password123\` for all):

| Email | Role | Credit Score |
|-------|------|--------------|
| john.doe@email.com | Borrower | 720 |
| jane.smith@email.com | Borrower | 680 |
| bob.johnson@email.com | Lender | 780 |
| alice.williams@email.com | Lender | 800 |
| admin@microlending.com | Admin | 850 |

**JWT Flow**:
1. POST \`/auth/login\` → receive JWT token
2. Store in localStorage
3. Include in requests: \`Authorization: Bearer <token>\`

## Database Management

### Reset Database
\`\`\`bash
# Drops all data
mysql -h <host> -u admin -p microlending < db/reset.sql
mysql -h <host> -u admin -p microlending < db/schema.sql
\`\`\`

### Verify Tables
\`\`\`bash
mysql -h <host> -u admin -p microlending -e "SHOW TABLES;"
mysql -h <host> -u admin -p microlending -e "DESCRIBE user;"
\`\`\`

## Midterm Demonstration

**File**: \`midterm_complete.py\`

Demonstrates 11 database admin requirements:

1. ✅ Database Objects (tables, constraints, indexes) - COMPLETE
2. ⏳ Data Manipulation (INSERT, UPDATE, DELETE)
3. ⏳ Advanced Queries (JOINs, subqueries, aggregations)
4. ⏳ Stored Procedures
5. ⏳ Functions
6. ⏳ Triggers
7. ⏳ Views
8. ⏳ Transactions & ACID
9. ⏳ User Management & Privileges
10. ⏳ Backup & Recovery
11. ⏳ Performance Optimization

**Usage**:
\`\`\`bash
python3 midterm_complete.py
# Output: MIDTERM_SUBMISSION.log
\`\`\`

## API Endpoints

Full documentation at http://localhost:8000/docs when backend is running.

### Authentication
- `POST /auth/login` - Login with email/password
- `POST /auth/refresh` - Refresh JWT token

### Users
- `POST /users` - Register new user
- `GET /users` - List all users
- `GET /users/{user_id}` - Get user details
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

### KYC & Wallets
- `POST /users/{user_id}/kyc` - Submit KYC data
- `GET /users/{user_id}/kyc` - Get KYC status
- `GET /users/{user_id}/accounts` - Get wallet accounts
- `POST /users/{user_id}/accounts` - Create wallet
- `GET /accounts/{account_id}/transactions` - Transaction history

### Loan Applications
- `GET /users/{user_id}/loan-application` - List applications
- `POST /users/{user_id}/loan-application` - Apply for loan
- `GET /users/{user_id}/loan-applications/{application_id}` - Get application
- `PUT /users/{user_id}/loan-applications/{application_id}` - Update application

### Loans & Payments
- `GET /users/{user_id}/loans` - User's loans
- `GET /users/{user_id}/loans/{loan_id}` - Loan details
- `GET /users/{user_id}/loans/{loan_id}/payments` - Payment schedule
- `POST /users/{user_id}/loans/{loan_id}/payments` - Make payment

### Admin
- `GET /admin/dashboard` - Platform metrics
- `GET /admin/loans/approval` - Pending approvals
- `POST /admin/loans/{loan_id}/approve` - Approve loan
- `POST /admin/loans/{loan_id}/reject` - Reject loan
- `GET /admin/audit-logs` - Audit trail
- `GET /admin/transactions` - All transactions

### Demo (Midterm)
- `POST /demo/transaction/success` - Successful transaction demo
- `POST /demo/transaction/failure` - Failed transaction (rollback)
- `GET /demo/query/explain` - EXPLAIN query analysis
- `GET /demo/audit/trail` - Audit log demo
- `POST /demo/constraint/violation` - Constraint violation demo
- \`POST /demo/transaction/success\` - Atomic transaction
- \`POST /demo/transaction/failure\` - Rollback demo
- \`GET /demo/query/explain\` - Query optimization
- \`GET /demo/audit/trail\` - Audit logging

## Testing

\`\`\`bash
# Run backend tests
pytest src/api_server/server_test.py

# Quick API test
curl http://localhost:8000/health
\`\`\`

## Troubleshooting

**"ModuleNotFoundError"**
\`\`\`bash
pip install -r requirements.txt
\`\`\`

**"Can't connect to MySQL"**
- Check network connection
- Verify \`.env\` credentials
- Test: \`mysql -h <host> -u admin -p\`

**"Address already in use"**
\`\`\`bash
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
\`\`\`

## Important Notes

- **Password Hashing**: SHA256 only (backend requires this, not bcrypt)
- **MySQL Version**: Requires 8.0+ for CHECK constraints
- **Ports**: Backend 8000, Frontend 3000
- **Schema**: \`db/schema.sql\` is the source of truth
- **Foreign Keys**: Mix of CASCADE and RESTRICT - check schema carefully

## Debugging

\`\`\`bash
# Check running servers
lsof -i :8000  # Backend
lsof -i :3000  # Frontend

# View logs
tail -f MIDTERM_SUBMISSION.log

# Connect to database
mysql -h micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com \
      -u admin -pmicropass microlending
\`\`\`


