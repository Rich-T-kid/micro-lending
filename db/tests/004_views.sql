use microlending;
SHOW FULL TABLES WHERE Table_type = 'VIEW';
SHOW CREATE VIEW v_active_loans;
SELECT * FROM v_active_loans LIMIT 3;
SHOW CREATE VIEW v_portfolio_dashboard;
SELECT user_id, full_name, role, wallet_balance, active_loans, total_amount_owed FROM v_portfolio_dashboard LIMIT 3;
SHOW CREATE VIEW v_user_profile_safe;
SELECT * FROM v_user_profile_safe LIMIT 3;
