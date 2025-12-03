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
    error_message TEXT NOT NULL,
    source_table VARCHAR(100),
    source_record_id VARCHAR(100),
    error_data JSON,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES etl_run_log(run_id),
    FOREIGN KEY (step_id) REFERENCES etl_step_log(step_id),
    INDEX idx_error_run (run_id),
    INDEX idx_error_type (error_type)
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
