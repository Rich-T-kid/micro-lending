-- Star Schema for Micro-Lending Analytics

-- Set CTE recursion limit for date generation (3 years = ~1095 days)
SET SESSION cte_max_recursion_depth = 2000;

-- DIMENSION TABLES

-- Date dimension for time-based analysis
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    week_of_year INT NOT NULL,
    day_of_month INT NOT NULL,
    day_of_week INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_month_end BOOLEAN NOT NULL,
    is_quarter_end BOOLEAN NOT NULL,
    fiscal_year INT NOT NULL,
    fiscal_quarter INT NOT NULL,
    INDEX idx_dim_date_year_month (year, month),
    INDEX idx_dim_date_quarter (year, quarter)
);

-- User dimension with denormalized attributes
CREATE TABLE IF NOT EXISTS dim_user (
    user_key INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL,
    credit_score INT,
    credit_tier VARCHAR(20),
    region_code VARCHAR(10),
    region_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    effective_date DATE NOT NULL,
    expiry_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    INDEX idx_dim_user_id (user_id),
    INDEX idx_dim_user_role (role),
    INDEX idx_dim_user_tier (credit_tier),
    INDEX idx_dim_user_current (is_current)
);

-- Loan product dimension
CREATE TABLE IF NOT EXISTS dim_loan_product (
    product_key INT AUTO_INCREMENT PRIMARY KEY,
    product_code VARCHAR(20) NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    term_category VARCHAR(20) NOT NULL,
    min_amount DECIMAL(15,2),
    max_amount DECIMAL(15,2),
    base_interest_rate DECIMAL(5,2),
    risk_tier VARCHAR(20),
    effective_date DATE NOT NULL,
    expiry_date DATE DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    INDEX idx_dim_product_code (product_code),
    INDEX idx_dim_product_category (category),
    INDEX idx_dim_product_current (is_current)
);

-- Currency dimension
CREATE TABLE IF NOT EXISTS dim_currency (
    currency_key INT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(3) NOT NULL UNIQUE,
    currency_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(5),
    decimal_places INT DEFAULT 2,
    is_base_currency BOOLEAN DEFAULT FALSE,
    INDEX idx_dim_currency_code (currency_code)
);

-- Loan status dimension
CREATE TABLE IF NOT EXISTS dim_loan_status (
    status_key INT AUTO_INCREMENT PRIMARY KEY,
    status_code VARCHAR(20) NOT NULL UNIQUE,
    status_name VARCHAR(50) NOT NULL,
    status_category VARCHAR(20) NOT NULL,
    is_terminal BOOLEAN DEFAULT FALSE,
    display_order INT
);

-- ============================================================================
-- FACT TABLES
-- ============================================================================

-- Loan transaction fact table
-- Note: Partitioned tables in MySQL cannot have foreign keys, so we use indexes 
-- and application-level referential integrity for dimension lookups
CREATE TABLE IF NOT EXISTS fact_loan_transactions (
    transaction_key BIGINT NOT NULL AUTO_INCREMENT,
    date_key INT NOT NULL,
    user_key INT NOT NULL,
    product_key INT NOT NULL,
    currency_key INT NOT NULL,
    status_key INT NOT NULL,
    loan_id INT NOT NULL,
    application_id INT,
    transaction_type VARCHAR(20) NOT NULL,
    principal_amount DECIMAL(15,2) NOT NULL,
    interest_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) NOT NULL,
    amount_usd DECIMAL(15,2) NOT NULL,
    interest_rate DECIMAL(5,2),
    term_months INT,
    outstanding_balance DECIMAL(15,2),
    fx_rate DECIMAL(15,6) DEFAULT 1.000000,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (transaction_key, date_key),
    INDEX idx_fact_loan_user (user_key),
    INDEX idx_fact_loan_product (product_key),
    INDEX idx_fact_loan_status (status_key),
    INDEX idx_fact_loan_type (transaction_type),
    INDEX idx_fact_loan_id (loan_id)
) PARTITION BY RANGE (date_key) (
    PARTITION p2024 VALUES LESS THAN (20250101),
    PARTITION p2025q1 VALUES LESS THAN (20250401),
    PARTITION p2025q2 VALUES LESS THAN (20250701),
    PARTITION p2025q3 VALUES LESS THAN (20251001),
    PARTITION p2025q4 VALUES LESS THAN (20260101),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- Daily portfolio snapshot fact table
CREATE TABLE IF NOT EXISTS fact_daily_portfolio (
    snapshot_key BIGINT AUTO_INCREMENT PRIMARY KEY,
    date_key INT NOT NULL,
    total_users INT NOT NULL,
    active_borrowers INT NOT NULL,
    active_lenders INT NOT NULL,
    total_loans INT NOT NULL,
    active_loans INT NOT NULL,
    total_principal DECIMAL(18,2) NOT NULL,
    total_outstanding DECIMAL(18,2) NOT NULL,
    total_repaid DECIMAL(18,2) NOT NULL,
    loans_originated_today INT DEFAULT 0,
    amount_originated_today DECIMAL(15,2) DEFAULT 0,
    payments_received_today DECIMAL(15,2) DEFAULT 0,
    loans_defaulted INT DEFAULT 0,
    loans_paid_off INT DEFAULT 0,
    default_rate DECIMAL(5,4) DEFAULT 0,
    delinquency_rate DECIMAL(5,4) DEFAULT 0,
    avg_loan_size DECIMAL(15,2),
    avg_interest_rate DECIMAL(5,2),
    weighted_avg_credit_score DECIMAL(5,1),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fact_portfolio_date (date_key),
    UNIQUE KEY uk_portfolio_date (date_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

-- POPULATE DIMENSION TABLES

-- Populate dim_date for 2024-2026
INSERT INTO dim_date (date_key, full_date, year, quarter, month, month_name, week_of_year, day_of_month, day_of_week, day_name, is_weekend, is_month_end, is_quarter_end, fiscal_year, fiscal_quarter)
WITH RECURSIVE dates AS (
    SELECT DATE('2024-01-01') AS dt
    UNION ALL
    SELECT dt + INTERVAL 1 DAY FROM dates WHERE dt < '2026-12-31'
)
SELECT 
    CAST(DATE_FORMAT(dt, '%Y%m%d') AS UNSIGNED) AS date_key,
    dt AS full_date,
    YEAR(dt) AS year,
    QUARTER(dt) AS quarter,
    MONTH(dt) AS month,
    MONTHNAME(dt) AS month_name,
    WEEK(dt) AS week_of_year,
    DAY(dt) AS day_of_month,
    DAYOFWEEK(dt) AS day_of_week,
    DAYNAME(dt) AS day_name,
    DAYOFWEEK(dt) IN (1, 7) AS is_weekend,
    dt = LAST_DAY(dt) AS is_month_end,
    dt = LAST_DAY(dt) AND MONTH(dt) IN (3, 6, 9, 12) AS is_quarter_end,
    YEAR(dt) AS fiscal_year,
    QUARTER(dt) AS fiscal_quarter
FROM dates;

-- Populate dim_currency
INSERT INTO dim_currency (currency_code, currency_name, symbol, decimal_places, is_base_currency) VALUES
('USD', 'US Dollar', '$', 2, TRUE),
('EUR', 'Euro', '€', 2, FALSE),
('GBP', 'British Pound', '£', 2, FALSE),
('CAD', 'Canadian Dollar', 'C$', 2, FALSE),
('MXN', 'Mexican Peso', '$', 2, FALSE);

-- Populate dim_loan_status
INSERT INTO dim_loan_status (status_code, status_name, status_category, is_terminal, display_order) VALUES
('pending', 'Pending Review', 'application', FALSE, 1),
('approved', 'Approved', 'application', FALSE, 2),
('rejected', 'Rejected', 'application', TRUE, 3),
('withdrawn', 'Withdrawn', 'application', TRUE, 4),
('active', 'Active', 'loan', FALSE, 5),
('paid_off', 'Paid Off', 'loan', TRUE, 6),
('defaulted', 'Defaulted', 'loan', TRUE, 7),
('cancelled', 'Cancelled', 'loan', TRUE, 8);

-- Populate dim_loan_product from reference data
INSERT INTO dim_loan_product (product_code, product_name, category, term_category, min_amount, max_amount, base_interest_rate, risk_tier, effective_date)
VALUES
('PERS_MICRO', 'Personal Micro Loan', 'personal', 'short', 100.00, 1000.00, 12.00, 'standard', '2024-01-01'),
('PERS_STD', 'Personal Standard Loan', 'personal', 'medium', 1000.00, 10000.00, 10.00, 'standard', '2024-01-01'),
('PERS_PLUS', 'Personal Plus Loan', 'personal', 'long', 5000.00, 25000.00, 8.50, 'prime', '2024-01-01'),
('BUS_START', 'Business Starter', 'business', 'short', 500.00, 5000.00, 14.00, 'standard', '2024-01-01'),
('BUS_GROW', 'Business Growth', 'business', 'medium', 5000.00, 50000.00, 11.00, 'prime', '2024-01-01'),
('EDU_TUITION', 'Education Tuition', 'education', 'long', 1000.00, 20000.00, 6.50, 'prime', '2024-01-01'),
('EMRG_QUICK', 'Emergency Quick Cash', 'emergency', 'short', 50.00, 500.00, 18.00, 'subprime', '2024-01-01'),
('AGRI_SEASON', 'Agricultural Seasonal', 'agriculture', 'short', 500.00, 10000.00, 9.00, 'standard', '2024-01-01');
