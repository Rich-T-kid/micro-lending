use microlending;
EXPLAIN SELECT * FROM user WHERE email = 'john.doe@email.com';
EXPLAIN SELECT * FROM user WHERE role = 'borrower';
EXPLAIN SELECT u.full_name, w.balance FROM user u JOIN wallet_account w ON u.id = w.user_id WHERE u.role = 'lender';
EXPLAIN SELECT u.full_name, l.principal_amount, l.status, l.created_at FROM user u JOIN loan l ON u.id = l.borrower_id WHERE l.status = 'active' ORDER BY l.created_at DESC LIMIT 10;
