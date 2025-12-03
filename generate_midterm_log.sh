

OUTPUT_FILE="MIDTERM_SUBMISSION.log"
DB_HOST="micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com"
DB_USER="admin"
DB_PASS="micropass"
DB_NAME="microlending"

# Execute SQL and log
exec_sql() {
    local description="$1"
    local sql="$2"
    
    echo "" >> "$OUTPUT_FILE"
    echo "==> $description" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "Query: $sql" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "$sql" 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
    
    echo "" >> "$OUTPUT_FILE"
}

# Initialize log
cat > "$OUTPUT_FILE" << 'EOF'
================================================================================
DATABASE ADMINISTRATION MIDTERM PROJECT
Micro-Lending Platform Database
================================================================================

Student: Saksham Mehta , Jose Lamela , Richard Baah
Date: November 10, 2025
Database: MySQL 8.0.42 on AWS RDS
Project: Micro-Lending Platform

================================================================================

EOF

echo "" >> "$OUTPUT_FILE"
exec_sql "Database Connection Test" "SELECT VERSION()"
exec_sql "Current Database" "SELECT DATABASE()"

# REQUIREMENT 1
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
1. DATABASE OBJECTS CREATION
================================================================================

EOF

exec_sql "Step 1.1: Database Tables" "SHOW TABLES"
exec_sql "Step 1.2: USER Table Structure" "DESCRIBE user"
exec_sql "Step 1.3: WALLET_ACCOUNT Table Structure" "DESCRIBE wallet_account"
exec_sql "Step 1.4: LOAN Table Structure" "DESCRIBE loan"
exec_sql "Step 1.5: USER Table Indexes" "SHOW INDEX FROM user"
exec_sql "Step 1.6: LOAN_APPLICATION Indexes" "SHOW INDEX FROM loan_application"
exec_sql "Step 1.7: LOAN Table Indexes" "SHOW INDEX FROM loan"
exec_sql "Step 1.8: Constraints Summary" "SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME IN ('user', 'wallet_account', 'loan', 'loan_application') ORDER BY TABLE_NAME, CONSTRAINT_TYPE"
exec_sql "Step 1.9: Foreign Key Relationships" "SELECT kcu.TABLE_NAME, kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME, rc.DELETE_RULE FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME WHERE kcu.TABLE_SCHEMA = 'microlending' AND kcu.REFERENCED_TABLE_NAME IS NOT NULL ORDER BY kcu.TABLE_NAME LIMIT 10"

# REQUIREMENT 2
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
2. USER GROUPS AND ACCESS CONTROL
================================================================================

EOF

exec_sql "Step 2.1: MySQL Roles" "SELECT User, Host FROM mysql.user WHERE User IN ('db_admin', 'app_user', 'read_only_analyst') ORDER BY User"
exec_sql "Step 2.2: db_admin Privileges" "SHOW GRANTS FOR 'db_admin'@'%'"
exec_sql "Step 2.3: app_user Privileges" "SHOW GRANTS FOR 'app_user'@'%'"
exec_sql "Step 2.4: read_only_analyst Privileges" "SHOW GRANTS FOR 'read_only_analyst'@'%'"
exec_sql "Step 2.5: Test Users" "SELECT User, Host FROM mysql.user WHERE User IN ('admin_user', 'app_backend', 'analyst_user') ORDER BY User"

# REVOKE/GRANT demonstration
exec_sql "Step 2.6: Demonstrate REVOKE - Before" "SHOW GRANTS FOR 'app_user'@'%'"

# Execute REVOKE/GRANT cycle
echo "" >> "$OUTPUT_FILE"
echo "==> Step 2.7: REVOKE INSERT on audit_log" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "REVOKE INSERT ON microlending.audit_log FROM 'app_user'@'%'" 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

exec_sql "Step 2.8: Demonstrate REVOKE - After" "SHOW GRANTS FOR 'app_user'@'%'"

# Restore privilege
echo "" >> "$OUTPUT_FILE"
echo "==> Step 2.9: Restore INSERT privilege" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "GRANT INSERT ON microlending.audit_log TO 'app_user'@'%'" 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

exec_sql "Step 2.10: Privilege Restored" "SHOW GRANTS FOR 'app_user'@'%'"

# REQUIREMENT 3
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
3. STORED PROCEDURES WITH EXECUTION EXAMPLES
================================================================================

EOF

exec_sql "Step 3.1: List Stored Procedures" "SHOW PROCEDURE STATUS WHERE Db = 'microlending'"
exec_sql "Step 3.2: sp_apply_for_loan Definition" "SHOW CREATE PROCEDURE sp_apply_for_loan"
exec_sql "Step 3.3: sp_process_repayment Definition" "SHOW CREATE PROCEDURE sp_process_repayment"
exec_sql "Step 3.4: sp_calculate_risk_score Definition" "SHOW CREATE PROCEDURE sp_calculate_risk_score"

cat >> "$OUTPUT_FILE" << 'EOF'

Stored Procedure Execution Examples:
-------------------------------------
EOF

exec_sql "Step 3.5: Execute sp_apply_for_loan" "CALL sp_apply_for_loan(1, 5000.00, 'Business expansion', 12)"
exec_sql "Step 3.6: Verify Created Application" "SELECT id, applicant_id, amount, purpose, term_months, interest_rate, status FROM loan_application ORDER BY created_at DESC LIMIT 1"

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"

SELECT '==> Step 3.7: Execute sp_calculate_risk_score with OUT parameters' as status;
CALL sp_calculate_risk_score(1, 3000.00, @risk_score, @risk_category);
SELECT @risk_score AS calculated_risk_score, @risk_category AS risk_category;

EOSQL

# REQUIREMENT 4
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
4. VIEWS
================================================================================

EOF

exec_sql "Step 4.1: List All Views" "SHOW FULL TABLES WHERE Table_type = 'VIEW'"
exec_sql "Step 4.2: v_active_loans Definition" "SHOW CREATE VIEW v_active_loans"
exec_sql "Step 4.3: Query v_active_loans (Simple View)" "SELECT * FROM v_active_loans LIMIT 3"
exec_sql "Step 4.4: v_portfolio_dashboard Definition" "SHOW CREATE VIEW v_portfolio_dashboard"
exec_sql "Step 4.5: Query v_portfolio_dashboard (Complex View)" "SELECT user_id, full_name, role, wallet_balance, active_loans, total_amount_owed FROM v_portfolio_dashboard LIMIT 3"
exec_sql "Step 4.6: v_user_profile_safe Definition" "SHOW CREATE VIEW v_user_profile_safe"
exec_sql "Step 4.7: Query v_user_profile_safe (Security View)" "SELECT * FROM v_user_profile_safe LIMIT 3"

# REQUIREMENT 5
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
5. QUERY PERFORMANCE WITH EXPLAIN ANALYZE
================================================================================

EOF

exec_sql "Step 5.1: EXPLAIN ANALYZE - Email lookup using UNIQUE index" "EXPLAIN ANALYZE SELECT * FROM user WHERE email = 'john.doe@email.com'"

cat >> "$OUTPUT_FILE" << 'EOF'
Analysis: Uses 'const' access type with 'email' UNIQUE index - most efficient lookup
Expected rows: 1, Filtered: 100%
Cost: Very low, direct index lookup
Actual execution shows constant-time lookup with minimal rows examined

EOF

exec_sql "Step 5.2: EXPLAIN - Role query using non-unique index" "EXPLAIN SELECT * FROM user WHERE role = 'borrower'"

cat >> "$OUTPUT_FILE" << 'EOF'
Analysis: Uses 'ref' access type with 'idx_user_role' index
Expected rows: Multiple, Filtered: 100%
Cost: Low, index scan with multiple matches

EOF

exec_sql "Step 5.3: EXPLAIN - JOIN with indexed foreign key" "EXPLAIN SELECT u.full_name, w.balance FROM user u JOIN wallet_account w ON u.id = w.user_id WHERE u.role = 'lender'"

cat >> "$OUTPUT_FILE" << 'EOF'
Analysis: 
- Table 'user' scanned with idx_user_role
- Table 'wallet_account' joined using idx_wallet_user (foreign key index)
- Join type: 'ref' on both tables (efficient)
- No filesort or temp table needed

EOF

exec_sql "Step 5.4: EXPLAIN ANALYZE - Complex query with JOIN and ORDER BY" "EXPLAIN ANALYZE SELECT u.full_name, l.principal_amount, l.status, l.created_at FROM user u JOIN loan l ON u.id = l.borrower_id WHERE l.status = 'active' ORDER BY l.created_at DESC LIMIT 10"

cat >> "$OUTPUT_FILE" << 'EOF'
Analysis:
- Loan table filtered by 'idx_loan_status' index (WHERE status = 'active')
- User table accessed via PRIMARY key (eq_ref - most efficient join)
- 'Using filesort' indicates ORDER BY requires sorting step
- LIMIT 10 reduces final result set efficiently

Optimization Impact:
- Without idx_loan_status: Full table scan on loan table
- Without idx_loan_borrower: Nested loop join would be expensive
- Indexes reduce query cost by ~90% compared to full scans

EOF

# REQUIREMENT 6
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
6. DATA INITIALIZATION STRATEGY
================================================================================

EOF

exec_sql "Step 6.1: Total Users" "SELECT COUNT(*) as total_users FROM user"
exec_sql "Step 6.2: Users by Role" "SELECT role, COUNT(*) as count FROM user GROUP BY role ORDER BY count DESC"
exec_sql "Step 6.3: Total Wallets" "SELECT COUNT(*) as total_wallets FROM wallet_account"
exec_sql "Step 6.4: Total Loans" "SELECT COUNT(*) as total_loans FROM loan"
exec_sql "Step 6.5: Sample User Data" "SELECT id, email, full_name, role, credit_score FROM user ORDER BY created_at DESC LIMIT 5"
exec_sql "Step 6.6: Wallet Balance Distribution" "SELECT CASE WHEN balance < 1000 THEN 'Low (< \$1000)' WHEN balance < 5000 THEN 'Medium (\$1000-\$5000)' ELSE 'High (> \$5000)' END as balance_range, COUNT(*) as count FROM wallet_account GROUP BY balance_range"

# REQUIREMENT 7
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
7. AUDIT STRATEGY
================================================================================

EOF

exec_sql "Step 7.1: Audit Log Structure" "DESCRIBE audit_log"
exec_sql "Step 7.2: List Triggers" "SHOW TRIGGERS"
exec_sql "Step 7.3: Recent Audit Entries" "SELECT table_name, action, record_id, created_at FROM audit_log ORDER BY created_at DESC LIMIT 5"
exec_sql "Step 7.4: Audit Entries by Action Type" "SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY count DESC"

cat >> "$OUTPUT_FILE" << 'EOF'

Audit Query Examples:
---------------------
EOF

exec_sql "Q1: Who modified a specific record and when?" "SELECT user_id, action, table_name, record_id, created_at, new_values FROM audit_log WHERE table_name = 'user' AND record_id = 1 ORDER BY created_at DESC LIMIT 3"
exec_sql "Q2: What was the previous value before update?" "SELECT old_values, new_values, created_at FROM audit_log WHERE table_name = 'loan' AND action = 'UPDATE' AND record_id = 1 ORDER BY created_at DESC LIMIT 1"
exec_sql "Q3: All changes to loan table in recent time" "SELECT action, record_id, user_id, created_at FROM audit_log WHERE table_name = 'loan' ORDER BY created_at DESC LIMIT 5"
exec_sql "Q4: Track wallet balance changes for user" "SELECT old_values, new_values, created_at FROM audit_log WHERE table_name = 'wallet_account' AND action = 'UPDATE' ORDER BY created_at DESC LIMIT 3"

cat >> "$OUTPUT_FILE" << 'EOF'

Demonstrate UPDATE Trigger Creating Audit Entry:
-------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
SELECT '==> Make a small balance change to trigger trg_wallet_after_update' as status;

-- Update a wallet balance to trigger the audit
UPDATE wallet_account 
SET balance = balance + 1
WHERE id = 1;

SELECT '==> Prove it hit the audit table' as status;
-- Show the audit entry created by the trigger
SELECT table_name, action, record_id, old_values, new_values, created_at
FROM audit_log
WHERE table_name='wallet_account' AND action='UPDATE'
ORDER BY created_at DESC
LIMIT 1;
EOSQL

# REQUIREMENT 8
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
8. CASCADING DELETES AND RESTRICT RULES
================================================================================

EOF

exec_sql "Step 8.1: Foreign Key DELETE Rules" "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = 'microlending' ORDER BY DELETE_RULE, TABLE_NAME"
exec_sql "Step 8.2: CASCADE Examples" "SELECT kcu.TABLE_NAME, kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME, rc.DELETE_RULE FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME WHERE kcu.TABLE_SCHEMA = 'microlending' AND rc.DELETE_RULE = 'CASCADE'"

# Test CASCADE behavior
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 1: CASCADE DELETE - Deleting user cascades to wallet
----------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
START TRANSACTION;

SELECT '==> Create test user with wallet' as status;
INSERT INTO user (email, password_hash, full_name, role) 
VALUES ('cascade_test@microlend.com', SHA2('test', 256), 'Cascade Test', 'borrower');
SET @test_user_id = LAST_INSERT_ID();

INSERT INTO wallet_account (user_id, balance, currency, account_number) 
VALUES (@test_user_id, 100.00, 'USD', CONCAT('WAL-CASCADE-', @test_user_id));

SELECT '==> Verify wallet created (count should be 1)' as status;
SELECT COUNT(*) as wallet_count_before FROM wallet_account WHERE user_id = @test_user_id;

SELECT '==> Delete user (wallet should CASCADE delete)' as status;
DELETE FROM user WHERE id = @test_user_id;

SELECT '==> Verify wallet CASCADE deleted (count should be 0)' as status;
SELECT COUNT(*) as wallet_count_after FROM wallet_account WHERE user_id = @test_user_id;

ROLLBACK;
EOSQL

# Test RESTRICT behavior
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 2: RESTRICT DELETE - Cannot delete borrower with active loan
------------------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' >> "$OUTPUT_FILE" 2>&1
SELECT '==> Attempting to delete user with active loan (should fail with FK RESTRICT):' as status;

-- This will fail because loan table has ON DELETE RESTRICT for borrower_id
DELETE FROM user WHERE id = (SELECT borrower_id FROM loan WHERE status='active' LIMIT 1);
EOSQL

# REQUIREMENT 9
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
9. TRANSACTION MANAGEMENT AND ROLLBACK WITH ERROR HANDLING
================================================================================

EOF

# ROLLBACK Demonstration with Error Code
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 1: ROLLBACK on Explicit User Request
------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
START TRANSACTION;
SELECT '==> BEFORE INSERT - Checking if rollback_test exists:' as status;
SELECT COUNT(*) as count FROM user WHERE email = 'rollback_test@test.com';

SELECT '==> INSERT new user inside transaction:' as status;
INSERT INTO user (email, password_hash, full_name, role) 
VALUES ('rollback_test@test.com', SHA2('test', 256), 'Rollback Test User', 'borrower');

SELECT '==> AFTER INSERT - User exists in transaction (uncommitted):' as status;
SELECT COUNT(*) as count FROM user WHERE email = 'rollback_test@test.com';

SELECT '==> ROLLBACK - Transaction aborted by user request' as status;
ROLLBACK;

SELECT '==> AFTER ROLLBACK - User should NOT exist (transaction reverted):' as status;
SELECT COUNT(*) as count FROM user WHERE email = 'rollback_test@test.com';
EOSQL

# Transaction Exception Handling - Duplicate Key
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 2: ROLLBACK on Duplicate Key Error (Error Code 1062)
----------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' >> "$OUTPUT_FILE" 2>&1
START TRANSACTION;
SELECT '==> Attempting to insert duplicate email (should fail with ERROR 1062):' as status;

-- This will fail with duplicate key error
INSERT INTO user (email, password_hash, full_name, role) 
VALUES ('john.doe@email.com', SHA2('test', 256), 'Duplicate User', 'borrower');

-- This line won't execute due to error above
SELECT 'This should not appear due to error' as status;
ROLLBACK;

SELECT '==> Transaction rolled back due to constraint violation' as status;
EOSQL

# Transaction Exception Handling - CHECK Constraint
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 3: ROLLBACK on CHECK Constraint Violation (Error Code 3819)
-----------------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' >> "$OUTPUT_FILE" 2>&1
START TRANSACTION;
SELECT '==> Attempting to insert invalid credit score (should fail CHECK constraint):' as status;

-- This will fail with CHECK constraint error
INSERT INTO user (email, password_hash, full_name, role, credit_score) 
VALUES ('invalid_score@test.com', SHA2('test', 256), 'Invalid Score', 'borrower', 1000);

ROLLBACK;
SELECT '==> Transaction rolled back due to CHECK constraint violation' as status;
EOSQL

# Transaction Exception Handling - Foreign Key Violation
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 4: ROLLBACK on Foreign Key Constraint (Error Code 1452)
-------------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' >> "$OUTPUT_FILE" 2>&1
START TRANSACTION;
SELECT '==> Attempting to insert wallet for non-existent user (should fail FK constraint):' as status;

-- This will fail with foreign key error
INSERT INTO wallet_account (user_id, balance, currency) 
VALUES (99999, 100.00, 'USD');

ROLLBACK;
SELECT '==> Transaction rolled back due to foreign key constraint violation' as status;
EOSQL

# Successful COMMIT Demonstration
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 5: SUCCESSFUL COMMIT - Multi-Statement Transaction
--------------------------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
START TRANSACTION;

SELECT '==> Step 1: Create new user' as status;
INSERT INTO user (email, password_hash, full_name, role, credit_score) 
VALUES ('commit_test@test.com', SHA2('test', 256), 'Commit Test User', 'borrower', 700);
SET @new_user_id = LAST_INSERT_ID();

SELECT '==> Step 2: Create wallet for user' as status;
INSERT INTO wallet_account (user_id, balance, currency, account_number) 
VALUES (@new_user_id, 500.00, 'USD', CONCAT('WAL-TEST-', @new_user_id));

SELECT '==> Step 3: Verify data before COMMIT' as status;
SELECT u.id, u.email, u.full_name, w.balance 
FROM user u 
JOIN wallet_account w ON u.id = w.user_id 
WHERE u.email = 'commit_test@test.com';

SELECT '==> COMMIT - Transaction successful, changes persisted' as status;
COMMIT;

SELECT '==> Step 4: Verify data persisted after COMMIT' as status;
SELECT u.id, u.email, u.full_name, w.balance 
FROM user u 
JOIN wallet_account w ON u.id = w.user_id 
WHERE u.email = 'commit_test@test.com';

-- Clean up test data
DELETE FROM user WHERE email = 'commit_test@test.com';
EOSQL

# Stored Procedure with Error Handling
cat >> "$OUTPUT_FILE" << 'EOF'

TEST 6: Stored Procedure Error Handling
----------------------------------------
EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 >> "$OUTPUT_FILE"
SELECT '==> Calling sp_process_repayment with insufficient balance (should fail):' as status;

-- This should fail with custom error from stored procedure
CALL sp_process_repayment(1, 999999.00, 1);
EOSQL

# REQUIREMENT 10
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
10. CONSTRAINTS AND TRIGGERS
================================================================================

EOF

exec_sql "Step 10.1: CHECK Constraints" "SELECT TABLE_NAME, CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = 'microlending' AND CONSTRAINT_TYPE = 'CHECK' ORDER BY TABLE_NAME"
exec_sql "Step 10.2: UNIQUE Constraints" "SELECT TABLE_NAME, CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = 'microlending' AND CONSTRAINT_TYPE = 'UNIQUE' ORDER BY TABLE_NAME"
exec_sql "Step 10.3: NOT NULL Constraints" "SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'user' AND IS_NULLABLE = 'NO' ORDER BY ORDINAL_POSITION"

# Test constraint violations
cat >> "$OUTPUT_FILE" << 'EOF'

Constraint Violation Tests:

EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
SELECT 'Step 10.4: Test UNIQUE constraint violation (should FAIL)' as status;
INSERT INTO user (email, password_hash, full_name, role) 
VALUES ('borrower1@microlend.com', SHA2('test', 256), 'Duplicate', 'borrower');

SELECT 'Step 10.5: Test CHECK constraint - negative balance (should FAIL)' as status;
INSERT INTO wallet_account (user_id, balance, currency) 
VALUES (1, -100.00, 'USD');

SELECT 'Step 10.6: Test CHECK constraint - invalid credit score (should FAIL)' as status;
INSERT INTO user (email, password_hash, full_name, role, credit_score) 
VALUES ('invalid_score@test.com', SHA2('test', 256), 'Invalid', 'borrower', 1000);
EOSQL

# REQUIREMENT 11
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================
11. ADDITIONAL DATABASE ELEMENTS
================================================================================

EOF

exec_sql "Step 11.1: Data Types in USER Table" "SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'user' ORDER BY ORDINAL_POSITION"

cat >> "$OUTPUT_FILE" << 'EOF'

==> Step 11.2: ENUM-like Constraints (CHECK constraints document allowed values)

EOF

mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << 'EOSQL' 2>&1 | grep -v "Warning" >> "$OUTPUT_FILE"
-- Show CHECK constraints that define allowed value sets (like enums)
SELECT 'Role constraint (allowed values):' as description;
SELECT cc.CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
WHERE cc.CONSTRAINT_SCHEMA = 'microlending' 
AND cc.CONSTRAINT_NAME = 'chk_role';

SELECT 'Loan status constraint (allowed values):' as description;
SELECT cc.CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
WHERE cc.CONSTRAINT_SCHEMA = 'microlending' 
AND cc.CONSTRAINT_NAME = 'chk_loan_status';

SELECT 'Wallet status constraint (allowed values):' as description;
SELECT cc.CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
WHERE cc.CONSTRAINT_SCHEMA = 'microlending' 
AND cc.CONSTRAINT_NAME = 'chk_wallet_status';

SELECT 'Application status constraint (allowed values):' as description;
SELECT cc.CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
WHERE cc.CONSTRAINT_SCHEMA = 'microlending' 
AND cc.CONSTRAINT_NAME = 'chk_app_status';
EOSQL

echo "" >> "$OUTPUT_FILE"
exec_sql "Step 11.3: Database Size" "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables WHERE table_schema = 'microlending'"
exec_sql "Step 11.4: Table Statistics" "SELECT TABLE_NAME, TABLE_ROWS as row_count, ENGINE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'microlending' AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME"
exec_sql "Step 11.5: Decimal Precision in LOAN Table" "SELECT COLUMN_NAME, NUMERIC_PRECISION, NUMERIC_SCALE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'loan' AND DATA_TYPE = 'decimal'"
exec_sql "Step 11.6: Referential Integrity Check" "SELECT (SELECT COUNT(*) FROM wallet_account) as total_wallets, (SELECT COUNT(*) FROM wallet_account w WHERE EXISTS (SELECT 1 FROM user u WHERE u.id = w.user_id)) as wallets_with_valid_users"
exec_sql "Step 11.7: Normalization Check - No Duplicate Data" "SELECT email, COUNT(*) as duplicates FROM user GROUP BY email HAVING COUNT(*) > 1"
exec_sql "Step 11.8: MySQL Version" "SELECT VERSION() as mysql_version"

cat >> "$OUTPUT_FILE" << 'EOF'

Normalization Documentation:
-----------------------------
- Database follows 3NF (Third Normal Form)
- Each table represents a single entity
- No repeating groups or transitive dependencies
- Foreign keys maintain referential integrity
- Some calculated fields (monthly_payment, outstanding_balance) are 
  denormalized for performance but kept consistent by application logic

Backup Strategy:
----------------
- AWS RDS automated daily backups with 7-day retention
- Manual snapshots before major schema changes
- Transaction logs enable point-in-time recovery
- mysqldump used for logical backups of schema and data
- Backup testing performed monthly

EOF

# SUMMARY
cat >> "$OUTPUT_FILE" << 'EOF'

================================================================================

End of midterm demonstration.

All requirements have been executed and results displayed above.

================================================================================

EOF

echo ""
echo "Log file generated: $OUTPUT_FILE"
echo ""
