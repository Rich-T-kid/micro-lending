-- ETL Control Tables

-- Tracks each ETL run
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id INT AUTO_INCREMENT PRIMARY KEY,
    run_type ENUM('full', 'incremental') NOT NULL,
    status ENUM('running', 'success', 'failed', 'partial') NOT NULL DEFAULT 'running',
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    rows_extracted INT DEFAULT 0,
    rows_transformed INT DEFAULT 0,
    rows_loaded INT DEFAULT 0,
    rows_rejected INT DEFAULT 0,
    error_message TEXT,
    INDEX idx_run_status (status),
    INDEX idx_run_started (started_at)
);

-- Tracks individual ETL steps within a run
CREATE TABLE IF NOT EXISTS etl_step_log (
    step_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    step_type ENUM('extract', 'transform', 'load', 'validate') NOT NULL,
    source_table VARCHAR(100),
    target_table VARCHAR(100),
    status ENUM('running', 'success', 'failed', 'skipped') NOT NULL DEFAULT 'running',
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    rows_processed INT DEFAULT 0,
    rows_inserted INT DEFAULT 0,
    rows_updated INT DEFAULT 0,
    rows_rejected INT DEFAULT 0,
    duration_seconds DECIMAL(10,2),
    error_message TEXT,
    FOREIGN KEY (run_id) REFERENCES etl_run_log(run_id),
    INDEX idx_step_run (run_id),
    INDEX idx_step_status (status)
);

-- Detailed error tracking
CREATE TABLE IF NOT EXISTS etl_error_log (
    error_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    step_id INT,
    error_type VARCHAR(50) NOT NULL,
    error_code VARCHAR(20),
    severity ENUM('INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL DEFAULT 'ERROR',
    process_name VARCHAR(100) NOT NULL DEFAULT 'etl',
    error_message TEXT NOT NULL,
    source_table VARCHAR(100),
    source_record_id VARCHAR(100),
    error_data JSON,
    stack_trace TEXT,
    correlation_id VARCHAR(50),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES etl_run_log(run_id),
    FOREIGN KEY (step_id) REFERENCES etl_step_log(step_id),
    INDEX idx_error_run (run_id),
    INDEX idx_error_type (error_type),
    INDEX idx_error_severity (severity),
    INDEX idx_error_process (process_name),
    INDEX idx_error_correlation (correlation_id)
);

-- High-water marks for incremental loads
CREATE TABLE IF NOT EXISTS etl_watermarks (
    watermark_id INT AUTO_INCREMENT PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL DEFAULT 'updated_at',
    watermark_value DATETIME,
    last_run_id INT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_watermark (source_name, table_name),
    FOREIGN KEY (last_run_id) REFERENCES etl_run_log(run_id)
);

-- Initialize watermarks for source tables
INSERT INTO etl_watermarks (source_name, table_name, column_name, watermark_value) VALUES
('transaction_db', 'user', 'updated_at', '1970-01-01 00:00:00'),
('transaction_db', 'loan', 'updated_at', '1970-01-01 00:00:00'),
('transaction_db', 'loan_application', 'updated_at', '1970-01-01 00:00:00'),
('transaction_db', 'wallet_account', 'updated_at', '1970-01-01 00:00:00'),
('transaction_db', 'transaction_ledger', 'created_at', '1970-01-01 00:00:00'),
('transaction_db', 'repayment_schedule', 'updated_at', '1970-01-01 00:00:00'),
('reference_db', 'ref_currency', 'created_at', '1970-01-01 00:00:00'),
('reference_db', 'ref_loan_product', 'created_at', '1970-01-01 00:00:00'),
('reference_db', 'ref_region', 'created_at', '1970-01-01 00:00:00'),
('reference_db', 'ref_credit_tier', 'created_at', '1970-01-01 00:00:00'),
('market_db', 'market_fx_rates', 'created_at', '1970-01-01 00:00:00'),
('market_db', 'market_interest_benchmarks', 'created_at', '1970-01-01 00:00:00'),
('market_db', 'market_credit_spreads', 'created_at', '1970-01-01 00:00:00')
ON DUPLICATE KEY UPDATE source_name = source_name;

-- ============================================================================
-- STAGING TABLES FOR HIGH-PERFORMANCE BULK LOADING
-- ============================================================================
-- Data flows: Extract -> Staging Tables -> Validate -> Target Tables
-- This approach enables bulk operations and avoids row-by-row processing

-- Staging table for user dimension
CREATE TABLE IF NOT EXISTS etl_staging_user (
    staging_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    user_id INT NOT NULL,
    email VARCHAR(255),
    full_name VARCHAR(255),
    role VARCHAR(50),
    credit_score INT,
    credit_tier VARCHAR(20),
    region_code VARCHAR(10),
    region_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_valid BOOLEAN DEFAULT NULL,
    validation_error VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_staging_user_run (run_id),
    INDEX idx_staging_user_valid (is_valid)
);

-- Staging table for loan transactions
CREATE TABLE IF NOT EXISTS etl_staging_loan (
    staging_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    loan_id INT NOT NULL,
    application_id INT,
    borrower_id INT NOT NULL,
    principal_amount DECIMAL(15,2),
    interest_rate DECIMAL(5,2),
    term_months INT,
    outstanding_balance DECIMAL(15,2),
    status VARCHAR(20),
    currency_code VARCHAR(3) DEFAULT 'USD',
    fx_rate DECIMAL(15,6) DEFAULT 1.000000,
    created_at DATETIME,
    is_valid BOOLEAN DEFAULT NULL,
    validation_error VARCHAR(255),
    staged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_staging_loan_run (run_id),
    INDEX idx_staging_loan_valid (is_valid)
);

-- Staging table for portfolio snapshot
CREATE TABLE IF NOT EXISTS etl_staging_portfolio (
    staging_id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    snapshot_date DATE NOT NULL,
    total_users INT,
    active_borrowers INT,
    active_lenders INT,
    total_loans INT,
    active_loans INT,
    total_principal DECIMAL(18,2),
    total_outstanding DECIMAL(18,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_staging_portfolio_run (run_id)
);

-- Stored procedure to clear staging tables for a new run
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_etl_clear_staging(IN p_run_id INT)
BEGIN
    DELETE FROM etl_staging_user WHERE run_id = p_run_id;
    DELETE FROM etl_staging_loan WHERE run_id = p_run_id;
    DELETE FROM etl_staging_portfolio WHERE run_id = p_run_id;
END //
DELIMITER ;

-- Stored procedure to validate staging data using SET-BASED operations
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_etl_validate_staging(
    IN p_run_id INT,
    OUT p_users_valid INT,
    OUT p_users_invalid INT,
    OUT p_loans_valid INT,
    OUT p_loans_invalid INT
)
BEGIN
    -- Validate users: check for required fields and valid enums
    UPDATE etl_staging_user
    SET is_valid = FALSE,
        validation_error = CASE
            WHEN user_id IS NULL THEN 'NULL_USER_ID'
            WHEN email IS NULL OR email = '' THEN 'NULL_EMAIL'
            WHEN role NOT IN ('borrower', 'lender', 'admin') THEN 'INVALID_ROLE'
            WHEN credit_score IS NOT NULL AND (credit_score < 300 OR credit_score > 850) THEN 'INVALID_CREDIT_SCORE'
            ELSE NULL
        END
    WHERE run_id = p_run_id;
    
    UPDATE etl_staging_user
    SET is_valid = TRUE
    WHERE run_id = p_run_id AND validation_error IS NULL;
    
    SELECT COUNT(*) INTO p_users_valid FROM etl_staging_user WHERE run_id = p_run_id AND is_valid = TRUE;
    SELECT COUNT(*) INTO p_users_invalid FROM etl_staging_user WHERE run_id = p_run_id AND is_valid = FALSE;
    
    -- Validate loans: check FK, ranges, enums using SET-BASED operations
    UPDATE etl_staging_loan sl
    LEFT JOIN user u ON sl.borrower_id = u.id
    LEFT JOIN dim_loan_status dls ON sl.status = dls.status_code
    SET sl.is_valid = FALSE,
        sl.validation_error = CASE
            WHEN sl.loan_id IS NULL THEN 'NULL_LOAN_ID'
            WHEN sl.borrower_id IS NULL THEN 'NULL_BORROWER'
            WHEN u.id IS NULL THEN 'INVALID_BORROWER_FK'
            WHEN sl.principal_amount IS NULL OR sl.principal_amount <= 0 THEN 'INVALID_PRINCIPAL'
            WHEN sl.interest_rate < 0 OR sl.interest_rate > 100 THEN 'INVALID_RATE'
            WHEN sl.term_months IS NULL OR sl.term_months <= 0 THEN 'INVALID_TERM'
            WHEN dls.status_key IS NULL THEN 'INVALID_STATUS'
            ELSE NULL
        END
    WHERE sl.run_id = p_run_id;
    
    UPDATE etl_staging_loan
    SET is_valid = TRUE
    WHERE run_id = p_run_id AND validation_error IS NULL;
    
    SELECT COUNT(*) INTO p_loans_valid FROM etl_staging_loan WHERE run_id = p_run_id AND is_valid = TRUE;
    SELECT COUNT(*) INTO p_loans_invalid FROM etl_staging_loan WHERE run_id = p_run_id AND is_valid = FALSE;
    
    -- Log invalid records to error log
    INSERT INTO etl_error_log (run_id, error_type, error_code, error_message, source_table, source_record_id)
    SELECT p_run_id, 'VALIDATION', validation_error, CONCAT('User validation failed: ', validation_error),
           'etl_staging_user', user_id
    FROM etl_staging_user WHERE run_id = p_run_id AND is_valid = FALSE;
    
    INSERT INTO etl_error_log (run_id, error_type, error_code, error_message, source_table, source_record_id)
    SELECT p_run_id, 'VALIDATION', validation_error, CONCAT('Loan validation failed: ', validation_error),
           'etl_staging_loan', loan_id
    FROM etl_staging_loan WHERE run_id = p_run_id AND is_valid = FALSE;
END //
DELIMITER ;

-- Stored procedure for BULK LOAD from staging to dimension (SET-BASED, not row-by-row!)
DELIMITER //
CREATE PROCEDURE IF NOT EXISTS sp_etl_bulk_load_dim_user(
    IN p_run_id INT,
    OUT p_rows_inserted INT,
    OUT p_rows_updated INT,
    OUT p_load_time_ms INT,
    OUT p_status VARCHAR(20),
    OUT p_message VARCHAR(255)
)
BEGIN
    DECLARE v_start_time DATETIME(3);
    DECLARE v_existing_count INT;
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS CONDITION 1 @err_msg = MESSAGE_TEXT;
        SET p_status = 'failed';
        SET p_message = @err_msg;
        ROLLBACK;
    END;
    
    SET v_start_time = NOW(3);
    SET p_rows_inserted = 0;
    SET p_rows_updated = 0;
    
    START TRANSACTION;
    
    -- STEP 1: Expire existing records that have changes (SCD Type 2)
    UPDATE dim_user du
    INNER JOIN etl_staging_user su ON du.user_id = su.user_id AND du.is_current = TRUE
    SET du.expiry_date = CURDATE(),
        du.is_current = FALSE
    WHERE su.run_id = p_run_id 
      AND su.is_valid = TRUE
      AND (du.email != su.email OR du.role != su.role OR 
           COALESCE(du.credit_score, 0) != COALESCE(su.credit_score, 0));
    
    SET p_rows_updated = ROW_COUNT();
    
    -- STEP 2: BULK INSERT new/changed records from staging (single INSERT...SELECT)
    INSERT INTO dim_user (user_id, email, full_name, role, credit_score, credit_tier,
                          region_code, region_name, is_active, effective_date, expiry_date, is_current)
    SELECT su.user_id, su.email, su.full_name, su.role, su.credit_score, su.credit_tier,
           su.region_code, su.region_name, su.is_active, CURDATE(), '9999-12-31', TRUE
    FROM etl_staging_user su
    LEFT JOIN dim_user du ON su.user_id = du.user_id AND du.is_current = TRUE
    WHERE su.run_id = p_run_id 
      AND su.is_valid = TRUE
      AND du.user_key IS NULL;  -- Only insert if not exists as current
    
    SET p_rows_inserted = ROW_COUNT();
    
    COMMIT;
    
    SET p_load_time_ms = TIMESTAMPDIFF(MICROSECOND, v_start_time, NOW(3)) / 1000;
    SET p_status = 'success';
    SET p_message = CONCAT('Bulk loaded dim_user: ', p_rows_inserted, ' inserted, ', 
                           p_rows_updated, ' updated in ', p_load_time_ms, 'ms');
END //
DELIMITER ;
