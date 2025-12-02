-- Market Data Source System
-- Provides external market rates and benchmarks for analytics

-- Foreign exchange rates
CREATE TABLE IF NOT EXISTS market_fx_rates (
    rate_id INT AUTO_INCREMENT PRIMARY KEY,
    base_currency VARCHAR(3) NOT NULL,
    quote_currency VARCHAR(3) NOT NULL,
    rate DECIMAL(15,6) NOT NULL,
    rate_date DATE NOT NULL,
    source VARCHAR(50) DEFAULT 'ECB',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fx_pair_date (base_currency, quote_currency, rate_date)
);

-- Interest rate benchmarks
CREATE TABLE IF NOT EXISTS market_interest_benchmarks (
    benchmark_id INT AUTO_INCREMENT PRIMARY KEY,
    benchmark_code VARCHAR(20) NOT NULL,
    benchmark_name VARCHAR(100) NOT NULL,
    rate DECIMAL(6,4) NOT NULL,
    effective_date DATE NOT NULL,
    term_months INT DEFAULT 1,
    source VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_benchmark_date (benchmark_code, effective_date, term_months)
);

-- Credit spread data by tier
CREATE TABLE IF NOT EXISTS market_credit_spreads (
    spread_id INT AUTO_INCREMENT PRIMARY KEY,
    tier_code VARCHAR(20) NOT NULL,
    product_category VARCHAR(20) NOT NULL,
    spread_bps INT NOT NULL,
    effective_date DATE NOT NULL,
    source VARCHAR(50) DEFAULT 'Internal',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_spread_tier_date (tier_code, product_category, effective_date)
);

-- Economic indicators
CREATE TABLE IF NOT EXISTS market_economic_indicators (
    indicator_id INT AUTO_INCREMENT PRIMARY KEY,
    indicator_code VARCHAR(20) NOT NULL,
    indicator_name VARCHAR(100) NOT NULL,
    value DECIMAL(15,4) NOT NULL,
    period_date DATE NOT NULL,
    region_code VARCHAR(10) DEFAULT 'USA',
    source VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_indicator_period (indicator_code, period_date, region_code)
);

-- Populate FX rates (USD base)
INSERT INTO market_fx_rates (base_currency, quote_currency, rate, rate_date, source) VALUES
('USD', 'EUR', 0.9234, '2025-12-01', 'ECB'),
('USD', 'GBP', 0.7891, '2025-12-01', 'ECB'),
('USD', 'CAD', 1.3542, '2025-12-01', 'ECB'),
('USD', 'MXN', 17.2450, '2025-12-01', 'ECB'),
('USD', 'JPY', 149.8500, '2025-12-01', 'ECB'),
('USD', 'INR', 83.4200, '2025-12-01', 'ECB'),
('USD', 'BRL', 4.9780, '2025-12-01', 'ECB'),
('USD', 'EUR', 0.9198, '2025-11-01', 'ECB'),
('USD', 'GBP', 0.7845, '2025-11-01', 'ECB'),
('USD', 'CAD', 1.3612, '2025-11-01', 'ECB'),
('USD', 'EUR', 0.9312, '2025-10-01', 'ECB'),
('USD', 'GBP', 0.7923, '2025-10-01', 'ECB'),
('USD', 'CAD', 1.3478, '2025-10-01', 'ECB');

-- Populate interest benchmarks
INSERT INTO market_interest_benchmarks (benchmark_code, benchmark_name, rate, effective_date, term_months, source) VALUES
('SOFR', 'Secured Overnight Financing Rate', 5.3300, '2025-12-01', 1, 'Federal Reserve'),
('SOFR', 'Secured Overnight Financing Rate', 5.3100, '2025-11-01', 1, 'Federal Reserve'),
('SOFR', 'Secured Overnight Financing Rate', 5.3500, '2025-10-01', 1, 'Federal Reserve'),
('PRIME', 'US Prime Rate', 8.5000, '2025-12-01', 1, 'Federal Reserve'),
('PRIME', 'US Prime Rate', 8.5000, '2025-11-01', 1, 'Federal Reserve'),
('PRIME', 'US Prime Rate', 8.5000, '2025-10-01', 1, 'Federal Reserve'),
('LIBOR_1M', '1-Month LIBOR', 5.4200, '2025-12-01', 1, 'ICE'),
('LIBOR_3M', '3-Month LIBOR', 5.5800, '2025-12-01', 3, 'ICE'),
('LIBOR_6M', '6-Month LIBOR', 5.7100, '2025-12-01', 6, 'ICE'),
('TREASURY_1Y', '1-Year Treasury', 4.8500, '2025-12-01', 12, 'US Treasury'),
('TREASURY_2Y', '2-Year Treasury', 4.4200, '2025-12-01', 24, 'US Treasury'),
('TREASURY_5Y', '5-Year Treasury', 4.2800, '2025-12-01', 60, 'US Treasury');

-- Populate credit spreads (basis points over benchmark)
INSERT INTO market_credit_spreads (tier_code, product_category, spread_bps, effective_date) VALUES
('EXCELLENT', 'personal', 150, '2025-12-01'),
('EXCELLENT', 'business', 175, '2025-12-01'),
('EXCELLENT', 'education', 100, '2025-12-01'),
('GOOD', 'personal', 300, '2025-12-01'),
('GOOD', 'business', 350, '2025-12-01'),
('GOOD', 'education', 200, '2025-12-01'),
('FAIR', 'personal', 550, '2025-12-01'),
('FAIR', 'business', 600, '2025-12-01'),
('FAIR', 'education', 400, '2025-12-01'),
('POOR', 'personal', 900, '2025-12-01'),
('POOR', 'business', 1000, '2025-12-01'),
('POOR', 'education', 700, '2025-12-01'),
('EXCELLENT', 'personal', 160, '2025-11-01'),
('GOOD', 'personal', 320, '2025-11-01'),
('FAIR', 'personal', 570, '2025-11-01'),
('POOR', 'personal', 920, '2025-11-01');

-- Populate economic indicators
INSERT INTO market_economic_indicators (indicator_code, indicator_name, value, period_date, region_code, source) VALUES
('UNEMPLOYMENT', 'Unemployment Rate', 3.7, '2025-11-01', 'USA', 'BLS'),
('UNEMPLOYMENT', 'Unemployment Rate', 3.8, '2025-10-01', 'USA', 'BLS'),
('UNEMPLOYMENT', 'Unemployment Rate', 3.8, '2025-09-01', 'USA', 'BLS'),
('CPI_YOY', 'CPI Year-over-Year', 3.2, '2025-11-01', 'USA', 'BLS'),
('CPI_YOY', 'CPI Year-over-Year', 3.4, '2025-10-01', 'USA', 'BLS'),
('GDP_GROWTH', 'GDP Growth Rate', 2.8, '2025-09-01', 'USA', 'BEA'),
('GDP_GROWTH', 'GDP Growth Rate', 3.0, '2025-06-01', 'USA', 'BEA'),
('CONSUMER_CONF', 'Consumer Confidence Index', 102.5, '2025-11-01', 'USA', 'Conference Board'),
('CONSUMER_CONF', 'Consumer Confidence Index', 99.8, '2025-10-01', 'USA', 'Conference Board'),
('DEFAULT_RATE', 'Consumer Loan Default Rate', 2.1, '2025-10-01', 'USA', 'Federal Reserve'),
('DELINQ_RATE', 'Consumer Loan Delinquency Rate', 3.4, '2025-10-01', 'USA', 'Federal Reserve');
