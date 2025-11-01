USE microlending;

SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'microlending'
ORDER BY DELETE_RULE, TABLE_NAME;

SELECT kcu.TABLE_NAME,
       kcu.COLUMN_NAME,
       kcu.REFERENCED_TABLE_NAME,
       kcu.REFERENCED_COLUMN_NAME,
       rc.DELETE_RULE
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS rc
  ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
 AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
WHERE kcu.TABLE_SCHEMA = 'microlending'
  AND rc.DELETE_RULE = 'CASCADE';

START TRANSACTION;

INSERT INTO `user` (email, password_hash, full_name, role)
VALUES ('cascade_test@microlend.com', SHA2('test', 256), 'Cascade Test', 'borrower');

SET @test_user_id = LAST_INSERT_ID();

INSERT INTO wallet_account (user_id, balance, currency)
VALUES (@test_user_id, 100.00, 'USD');

SELECT COUNT(*) AS wallet_count_before
FROM wallet_account
WHERE user_id = @test_user_id;

DELETE FROM `user`
WHERE id = @test_user_id;

SELECT COUNT(*) AS wallet_count_after
FROM wallet_account
WHERE user_id = @test_user_id;

ROLLBACK;
