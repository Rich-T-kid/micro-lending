USE microlending;
SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'user' ORDER BY ORDINAL_POSITION;
SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_mb FROM information_schema.tables WHERE table_schema = 'microlending';
SELECT TABLE_NAME, TABLE_ROWS as row_count, ENGINE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'microlending' AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME;
SELECT COLUMN_NAME, NUMERIC_PRECISION, NUMERIC_SCALE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'microlending' AND TABLE_NAME = 'loan' AND DATA_TYPE = 'decimal';
SELECT (SELECT COUNT(*) FROM wallet_account) as total_wallets, (SELECT COUNT(*) FROM wallet_account w WHERE EXISTS (SELECT 1 FROM user u WHERE u.id = w.user_id)) as wallets_with_valid_users;
SELECT email, COUNT(*) as duplicates FROM user GROUP BY email HAVING COUNT(*) > 1;
SELECT VERSION() as mysql_version;
