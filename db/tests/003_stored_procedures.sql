use microlending;
SHOW PROCEDURE STATUS WHERE Db = 'microlending';
SHOW CREATE PROCEDURE sp_apply_for_loan;
SHOW CREATE PROCEDURE sp_process_repayment;
SHOW CREATE PROCEDURE sp_calculate_risk_score;
CALL sp_apply_for_loan(1, 5000.00, 'Business expansion', 12);
SELECT * FROM loan_application ORDER BY created_at DESC LIMIT 1;
