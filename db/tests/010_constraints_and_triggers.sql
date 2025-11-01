USE microlending;

SELECT TABLE_NAME, CONSTRAINT_NAME
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'microlending' AND CONSTRAINT_TYPE = 'CHECK'
ORDER BY TABLE_NAME;

SELECT TABLE_NAME, CONSTRAINT_NAME
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = 'microlending' AND CONSTRAINT_TYPE = 'UNIQUE'
ORDER BY TABLE_NAME;

SELECT TABLE_NAME, COLUMN_NAME
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'user' AND IS_NULLABLE = 'NO'
ORDER BY ORDINAL_POSITION;

SELECT 'Test UNIQUE constraint violation (should FAIL)' AS status;
INSERT INTO `user` (email, password_hash, full_name, role)
VALUES ('borrower1@microlend.com', SHA2('test', 256), 'Duplicate', 'borrower');

SELECT 'Test CHECK constraint - negative balance (should FAIL)' AS status;
INSERT INTO wallet_account (user_id, balance, currency)
VALUES (1, -100.00, 'USD');

SELECT 'Test CHECK constraint - invalid credit score (should FAIL)' AS status;
INSERT INTO `user` (email, password_hash, full_name, role, credit_score)
VALUES ('invalid_score@test.com', SHA2('test', 256), 'Invalid', 'borrower', 1000);
