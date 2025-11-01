USE microlending;
SELECT COUNT(*) as total_users FROM user;
SELECT role, COUNT(*) as count FROM user GROUP BY role ORDER BY count DESC;
SELECT COUNT(*) as total_wallets FROM wallet_account;
SELECT COUNT(*) as total_loans FROM loan;
SELECT id, email, full_name, role, credit_score FROM user ORDER BY created_at DESC LIMIT 5;
SELECT CASE WHEN balance < 1000 THEN 'Low (< $1000)' WHEN balance < 5000 THEN 'Medium ($1000-$5000)' ELSE 'High (> $5000)' END as balance_range, COUNT(*) as count FROM wallet_account GROUP BY balance_range;
