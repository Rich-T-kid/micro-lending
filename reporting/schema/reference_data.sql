-- Reference Data Source System
-- Provides static lookup tables for the analytics layer

-- Currency reference table
CREATE TABLE IF NOT EXISTS ref_currency (
    currency_code VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(5),
    decimal_places INT DEFAULT 2,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Loan product types
CREATE TABLE IF NOT EXISTS ref_loan_product (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_code VARCHAR(20) NOT NULL UNIQUE,
    product_name VARCHAR(100) NOT NULL,
    category ENUM('personal', 'business', 'education', 'emergency', 'agriculture') NOT NULL,
    min_amount DECIMAL(15,2) NOT NULL,
    max_amount DECIMAL(15,2) NOT NULL,
    min_term_months INT NOT NULL,
    max_term_months INT NOT NULL,
    base_interest_rate DECIMAL(5,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Geographic regions
CREATE TABLE IF NOT EXISTS ref_region (
    region_id INT AUTO_INCREMENT PRIMARY KEY,
    region_code VARCHAR(10) NOT NULL UNIQUE,
    region_name VARCHAR(100) NOT NULL,
    region_type ENUM('state', 'country', 'territory') NOT NULL,
    parent_region_id INT,
    timezone VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_region_id) REFERENCES ref_region(region_id)
);

-- Credit tier classifications
CREATE TABLE IF NOT EXISTS ref_credit_tier (
    tier_id INT AUTO_INCREMENT PRIMARY KEY,
    tier_code VARCHAR(20) NOT NULL UNIQUE,
    tier_name VARCHAR(50) NOT NULL,
    min_score INT NOT NULL,
    max_score INT NOT NULL,
    risk_weight DECIMAL(5,4) NOT NULL,
    default_probability DECIMAL(5,4) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Populate currency data
INSERT INTO ref_currency (currency_code, currency_name, symbol, decimal_places) VALUES
('USD', 'US Dollar', '$', 2),
('EUR', 'Euro', '€', 2),
('GBP', 'British Pound', '£', 2),
('CAD', 'Canadian Dollar', 'C$', 2),
('MXN', 'Mexican Peso', '$', 2),
('JPY', 'Japanese Yen', '¥', 0),
('INR', 'Indian Rupee', '₹', 2),
('BRL', 'Brazilian Real', 'R$', 2);

-- Populate loan products
INSERT INTO ref_loan_product (product_code, product_name, category, min_amount, max_amount, min_term_months, max_term_months, base_interest_rate) VALUES
('PERS_MICRO', 'Personal Micro Loan', 'personal', 100.00, 1000.00, 1, 6, 12.00),
('PERS_STD', 'Personal Standard Loan', 'personal', 1000.00, 10000.00, 6, 24, 10.00),
('PERS_PLUS', 'Personal Plus Loan', 'personal', 5000.00, 25000.00, 12, 48, 8.50),
('BUS_START', 'Business Starter', 'business', 500.00, 5000.00, 3, 12, 14.00),
('BUS_GROW', 'Business Growth', 'business', 5000.00, 50000.00, 12, 36, 11.00),
('EDU_TUITION', 'Education Tuition', 'education', 1000.00, 20000.00, 12, 60, 6.50),
('EDU_BOOKS', 'Education Supplies', 'education', 100.00, 2000.00, 3, 12, 8.00),
('EMRG_QUICK', 'Emergency Quick Cash', 'emergency', 50.00, 500.00, 1, 3, 18.00),
('AGRI_SEASON', 'Agricultural Seasonal', 'agriculture', 500.00, 10000.00, 3, 12, 9.00),
('AGRI_EQUIP', 'Agricultural Equipment', 'agriculture', 2000.00, 30000.00, 12, 48, 7.50);

-- Populate regions (US states + select countries)
INSERT INTO ref_region (region_code, region_name, region_type, timezone) VALUES
('USA', 'United States', 'country', 'America/New_York'),
('CAN', 'Canada', 'country', 'America/Toronto'),
('MEX', 'Mexico', 'country', 'America/Mexico_City'),
('GBR', 'United Kingdom', 'country', 'Europe/London');

INSERT INTO ref_region (region_code, region_name, region_type, parent_region_id, timezone) VALUES
('NY', 'New York', 'state', 1, 'America/New_York'),
('CA', 'California', 'state', 1, 'America/Los_Angeles'),
('TX', 'Texas', 'state', 1, 'America/Chicago'),
('FL', 'Florida', 'state', 1, 'America/New_York'),
('IL', 'Illinois', 'state', 1, 'America/Chicago'),
('PA', 'Pennsylvania', 'state', 1, 'America/New_York'),
('OH', 'Ohio', 'state', 1, 'America/New_York'),
('GA', 'Georgia', 'state', 1, 'America/New_York'),
('NC', 'North Carolina', 'state', 1, 'America/New_York'),
('MI', 'Michigan', 'state', 1, 'America/Detroit');

-- Populate credit tiers
INSERT INTO ref_credit_tier (tier_code, tier_name, min_score, max_score, risk_weight, default_probability) VALUES
('EXCELLENT', 'Excellent', 750, 850, 0.2000, 0.0100),
('GOOD', 'Good', 650, 749, 0.4000, 0.0300),
('FAIR', 'Fair', 550, 649, 0.7000, 0.0800),
('POOR', 'Poor', 300, 549, 1.0000, 0.1500),
('NO_SCORE', 'No Score', 0, 0, 1.2000, 0.2000);
