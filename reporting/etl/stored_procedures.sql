-- ETL Stored Procedures

DELIMITER //

-- Validates a loan record before loading
CREATE PROCEDURE sp_etl_validate_loan(
    IN p_loan_id INT,
    IN p_borrower_id INT,
    IN p_principal_amount DECIMAL(15,2),
    IN p_interest_rate DECIMAL(5,2),
    IN p_term_months INT,
    IN p_status VARCHAR(20),
    OUT p_is_valid BOOLEAN,
    OUT p_error_code VARCHAR(20),
    OUT p_error_message VARCHAR(255)
)
BEGIN
    SET p_is_valid = TRUE;
    SET p_error_code = NULL;
    SET p_error_message = NULL;
    
    IF p_loan_id IS NULL THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'NULL_LOAN_ID';
        SET p_error_message = 'Loan ID cannot be null';
    ELSEIF p_borrower_id IS NULL THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'NULL_BORROWER';
        SET p_error_message = 'Borrower ID cannot be null';
    ELSEIF NOT EXISTS (SELECT 1 FROM user WHERE id = p_borrower_id) THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'INVALID_BORROWER';
        SET p_error_message = CONCAT('Borrower ID ', p_borrower_id, ' does not exist');
    ELSEIF p_principal_amount IS NULL OR p_principal_amount <= 0 THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'INVALID_PRINCIPAL';
        SET p_error_message = 'Principal amount must be positive';
    ELSEIF p_interest_rate IS NULL OR p_interest_rate < 0 OR p_interest_rate > 100 THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'INVALID_RATE';
        SET p_error_message = 'Interest rate must be between 0 and 100';
    ELSEIF p_term_months IS NULL OR p_term_months <= 0 THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'INVALID_TERM';
        SET p_error_message = 'Term months must be positive';
    ELSEIF p_status NOT IN ('pending', 'approved', 'rejected', 'withdrawn', 'active', 'paid_off', 'defaulted', 'cancelled') THEN
        SET p_is_valid = FALSE;
        SET p_error_code = 'INVALID_STATUS';
        SET p_error_message = CONCAT('Invalid status: ', p_status);
    END IF;
END //


-- Bulk loads loan transactions into fact table
CREATE PROCEDURE sp_etl_load_fact_transactions(
    IN p_run_id INT,
    IN p_batch_size INT,
    OUT p_rows_loaded INT,
    OUT p_rows_rejected INT,
    OUT p_status VARCHAR(20),
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_start_time DATETIME;
    DECLARE v_duration DECIMAL(10,2);
    DECLARE v_step_id INT;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 @err_msg = MESSAGE_TEXT;
        SET p_status = 'failed';
        SET p_message = @err_msg;
        
        UPDATE etl_step_log 
        SET status = 'failed', 
            completed_at = NOW(),
            error_message = @err_msg
        WHERE step_id = v_step_id;
        
        ROLLBACK;
    END;
    
    SET v_start_time = NOW();
    SET p_rows_loaded = 0;
    SET p_rows_rejected = 0;
    
    INSERT INTO etl_step_log (run_id, step_name, step_type, source_table, target_table, status)
    VALUES (p_run_id, 'load_fact_transactions', 'load', 'etl_staging', 'fact_loan_transactions', 'running');
    SET v_step_id = LAST_INSERT_ID();
    
    START TRANSACTION;
    
    INSERT INTO fact_loan_transactions (
        date_key, user_key, product_key, currency_key, status_key,
        loan_id, application_id, transaction_type, principal_amount,
        interest_amount, total_amount, amount_usd, interest_rate,
        term_months, outstanding_balance, fx_rate
    )
    SELECT 
        CAST(DATE_FORMAT(COALESCE(l.created_at, NOW()), '%Y%m%d') AS UNSIGNED) as date_key,
        COALESCE(du.user_key, 1) as user_key,
        COALESCE(dp.product_key, 1) as product_key,
        1 as currency_key,
        COALESCE(ds.status_key, 5) as status_key,
        l.id as loan_id,
        l.application_id,
        'origination' as transaction_type,
        l.principal_amount,
        ROUND(l.principal_amount * (l.interest_rate / 100) * (l.term_months / 12), 2) as interest_amount,
        l.principal_amount + ROUND(l.principal_amount * (l.interest_rate / 100) * (l.term_months / 12), 2) as total_amount,
        l.principal_amount as amount_usd,
        l.interest_rate,
        l.term_months,
        l.outstanding_balance,
        1.000000 as fx_rate
    FROM loan l
    LEFT JOIN dim_user du ON l.borrower_id = du.user_id AND du.is_current = TRUE
    LEFT JOIN dim_loan_product dp ON dp.is_current = TRUE
    LEFT JOIN dim_loan_status ds ON l.status = ds.status_code
    WHERE NOT EXISTS (
        SELECT 1 FROM fact_loan_transactions f WHERE f.loan_id = l.id AND f.transaction_type = 'origination'
    )
    LIMIT p_batch_size;
    
    SET p_rows_loaded = ROW_COUNT();
    
    COMMIT;
    
    SET v_duration = TIMESTAMPDIFF(SECOND, v_start_time, NOW());
    SET p_status = 'success';
    SET p_message = CONCAT('Loaded ', p_rows_loaded, ' rows in ', v_duration, ' seconds');
    
    UPDATE etl_step_log 
    SET status = 'success',
        completed_at = NOW(),
        rows_processed = p_rows_loaded,
        rows_inserted = p_rows_loaded,
        duration_seconds = v_duration
    WHERE step_id = v_step_id;
    
END //


-- Refreshes the daily portfolio snapshot
CREATE PROCEDURE sp_etl_refresh_portfolio_snapshot(
    IN p_snapshot_date DATE,
    OUT p_status VARCHAR(20),
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_date_key INT;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 @err_msg = MESSAGE_TEXT;
        SET p_status = 'failed';
        SET p_message = @err_msg;
        ROLLBACK;
    END;
    
    SET v_date_key = CAST(DATE_FORMAT(p_snapshot_date, '%Y%m%d') AS UNSIGNED);
    
    START TRANSACTION;
    
    DELETE FROM fact_daily_portfolio WHERE date_key = v_date_key;
    
    INSERT INTO fact_daily_portfolio (
        date_key, total_users, active_borrowers, active_lenders,
        total_loans, active_loans, total_principal, total_outstanding,
        total_repaid, loans_defaulted, loans_paid_off, default_rate,
        avg_loan_size, avg_interest_rate, weighted_avg_credit_score
    )
    SELECT 
        v_date_key,
        (SELECT COUNT(*) FROM user),
        (SELECT COUNT(*) FROM user WHERE role = 'borrower'),
        (SELECT COUNT(*) FROM user WHERE role = 'lender'),
        COUNT(*) as total_loans,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_loans,
        SUM(principal_amount) as total_principal,
        SUM(CASE WHEN status = 'active' THEN outstanding_balance ELSE 0 END) as total_outstanding,
        SUM(principal_amount) - SUM(CASE WHEN status = 'active' THEN outstanding_balance ELSE 0 END) as total_repaid,
        SUM(CASE WHEN status = 'defaulted' THEN 1 ELSE 0 END) as loans_defaulted,
        SUM(CASE WHEN status = 'paid_off' THEN 1 ELSE 0 END) as loans_paid_off,
        ROUND(SUM(CASE WHEN status = 'defaulted' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 4) as default_rate,
        ROUND(AVG(principal_amount), 2) as avg_loan_size,
        ROUND(AVG(interest_rate), 2) as avg_interest_rate,
        ROUND((SELECT AVG(credit_score) FROM user WHERE credit_score IS NOT NULL), 1) as weighted_avg_credit_score
    FROM loan;
    
    COMMIT;
    
    SET p_status = 'success';
    SET p_message = CONCAT('Portfolio snapshot refreshed for ', p_snapshot_date);
    
END //


DELIMITER ;
