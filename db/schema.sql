-- =============================================================================
-- MICRO-LENDING PLATFORM - DATABASE SCHEMA
-- =============================================================================
-- Database Administration Midterm Project
-- Single source of truth for the complete database schema
--
-- Tables: 8 core tables with full constraints and indexes
-- Demo Data: 6 users, loans, transactions ready for testing
-- 
-- To apply: mysql -h <host> -u admin -p microlending < schema.sql
-- =============================================================================

USE microlending;

-- =============================================================================
-- CORE TABLES (8)
-- =============================================================================

-- 1. USER ACCOUNTS
CREATE TABLE IF NOT EXISTS user (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'borrower',
    phone VARCHAR(20),
    address TEXT,
    credit_score INT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_credit_score CHECK (credit_score >= 300 AND credit_score <= 850),
    CONSTRAINT chk_role CHECK (role IN ('borrower', 'lender', 'admin')),
    INDEX idx_user_email (email),
    INDEX idx_user_role (role),
    INDEX idx_user_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. WALLET ACCOUNTS
CREATE TABLE IF NOT EXISTS wallet_account (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    balance DECIMAL(15, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    account_number VARCHAR(50) UNIQUE,
    status VARCHAR(20) DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    CONSTRAINT chk_balance_positive CHECK (balance >= 0),
    CONSTRAINT chk_wallet_status CHECK (status IN ('active', 'frozen', 'closed')),
    INDEX idx_wallet_user (user_id),
    INDEX idx_wallet_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. KYC VERIFICATION DATA
CREATE TABLE IF NOT EXISTS kyc_data (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    document_type VARCHAR(50),
    document_number VARCHAR(100),
    verification_status VARCHAR(20) DEFAULT 'pending',
    verified_at DATETIME NULL,
    verified_by INT NULL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    FOREIGN KEY (verified_by) REFERENCES user(id) ON DELETE SET NULL,
    CONSTRAINT chk_kyc_status CHECK (verification_status IN ('pending', 'approved', 'rejected')),
    INDEX idx_kyc_user (user_id),
    INDEX idx_kyc_status (verification_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. LOAN APPLICATIONS
CREATE TABLE IF NOT EXISTS loan_application (
    id INT PRIMARY KEY AUTO_INCREMENT,
    applicant_id INT NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    purpose TEXT,
    term_months INT NOT NULL,
    interest_rate DECIMAL(5, 2),
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_by INT NULL,
    reviewed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (applicant_id) REFERENCES user(id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewed_by) REFERENCES user(id) ON DELETE SET NULL,
    CONSTRAINT chk_loan_amount CHECK (amount > 0),
    CONSTRAINT chk_term_months CHECK (term_months > 0),
    CONSTRAINT chk_interest_rate CHECK (interest_rate >= 0 AND interest_rate <= 100),
    CONSTRAINT chk_app_status CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
    INDEX idx_app_applicant (applicant_id),
    INDEX idx_app_status (status),
    INDEX idx_app_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. LOANS
CREATE TABLE IF NOT EXISTS loan (
    id INT PRIMARY KEY AUTO_INCREMENT,
    application_id INT,
    borrower_id INT NOT NULL,
    lender_id INT,
    principal_amount DECIMAL(15, 2) NOT NULL,
    interest_rate DECIMAL(5, 2) NOT NULL,
    term_months INT NOT NULL,
    monthly_payment DECIMAL(15, 2),
    outstanding_balance DECIMAL(15, 2),
    status VARCHAR(20) DEFAULT 'active',
    disbursed_at DATETIME,
    maturity_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (application_id) REFERENCES loan_application(id) ON DELETE SET NULL,
    FOREIGN KEY (borrower_id) REFERENCES user(id) ON DELETE RESTRICT,
    FOREIGN KEY (lender_id) REFERENCES user(id) ON DELETE SET NULL,
    CONSTRAINT chk_principal_positive CHECK (principal_amount > 0),
    CONSTRAINT chk_loan_interest_rate CHECK (interest_rate >= 0 AND interest_rate <= 100),
    CONSTRAINT chk_loan_term CHECK (term_months > 0),
    CONSTRAINT chk_outstanding_balance CHECK (outstanding_balance >= 0),
    CONSTRAINT chk_loan_status CHECK (status IN ('active', 'paid_off', 'defaulted', 'cancelled')),
    INDEX idx_loan_borrower (borrower_id),
    INDEX idx_loan_lender (lender_id),
    INDEX idx_loan_status (status),
    INDEX idx_loan_maturity (maturity_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. TRANSACTION LEDGER
CREATE TABLE IF NOT EXISTS transaction_ledger (
    id INT PRIMARY KEY AUTO_INCREMENT,
    wallet_id INT NOT NULL,
    loan_id INT,
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    balance_before DECIMAL(15, 2),
    balance_after DECIMAL(15, 2),
    description TEXT,
    reference_number VARCHAR(100) UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (wallet_id) REFERENCES wallet_account(id) ON DELETE CASCADE,
    FOREIGN KEY (loan_id) REFERENCES loan(id) ON DELETE SET NULL,
    CONSTRAINT chk_trans_type CHECK (transaction_type IN ('deposit', 'withdrawal', 'loan_disbursement', 'loan_repayment', 'fee', 'interest', 'transfer')),
    INDEX idx_trans_wallet (wallet_id),
    INDEX idx_trans_loan (loan_id),
    INDEX idx_trans_type (transaction_type),
    INDEX idx_trans_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. REPAYMENT SCHEDULE
CREATE TABLE IF NOT EXISTS repayment_schedule (
    id INT PRIMARY KEY AUTO_INCREMENT,
    loan_id INT NOT NULL,
    installment_number INT NOT NULL,
    due_date DATE NOT NULL,
    principal_amount DECIMAL(15, 2) NOT NULL,
    interest_amount DECIMAL(15, 2) NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    paid_amount DECIMAL(15, 2) DEFAULT 0.00,
    paid_at DATETIME NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (loan_id) REFERENCES loan(id) ON DELETE CASCADE,
    CONSTRAINT chk_principal_nonnegative CHECK (principal_amount >= 0),
    CONSTRAINT chk_interest_nonnegative CHECK (interest_amount >= 0),
    CONSTRAINT chk_paid_amount_nonnegative CHECK (paid_amount >= 0),
    CONSTRAINT chk_repay_status CHECK (status IN ('pending', 'paid', 'overdue', 'partial')),
    INDEX idx_repay_loan (loan_id),
    INDEX idx_repay_due (due_date),
    INDEX idx_repay_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. AUDIT LOG
CREATE TABLE IF NOT EXISTS audit_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(50),
    record_id INT,
    old_values TEXT,
    new_values TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE SET NULL,
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_table (table_name, record_id),
    INDEX idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- DEMO DATA (For Testing & Development)
-- =============================================================================
-- Password for all users: password123
-- SHA256 hash: ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f

INSERT INTO user (id, email, password_hash, full_name, role, phone, address, credit_score, is_active, created_at) VALUES
(1, 'john.doe@email.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'John Doe', 'borrower', '+1-555-0101', '123 Main St, New York, NY 10001', 720, TRUE, '2024-01-15 10:00:00'),
(2, 'jane.smith@email.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'Jane Smith', 'borrower', '+1-555-0102', '456 Oak Ave, Los Angeles, CA 90001', 680, TRUE, '2024-01-20 11:30:00'),
(3, 'mike.brown@email.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'Mike Brown', 'borrower', '+1-555-0103', '789 Pine Rd, Chicago, IL 60601', 650, TRUE, '2024-02-01 09:15:00'),
(4, 'bob.johnson@email.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'Bob Johnson', 'lender', '+1-555-0201', '321 Elm St, Boston, MA 02101', 780, TRUE, '2024-01-10 08:00:00'),
(5, 'alice.williams@email.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'Alice Williams', 'lender', '+1-555-0202', '654 Maple Dr, Seattle, WA 98101', 800, TRUE, '2024-01-12 14:20:00'),
(6, 'admin@microlending.com', 'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', 
 'System Admin', 'admin', '+1-555-0001', '100 Corporate Blvd, Austin, TX 78701', 850, TRUE, '2024-01-01 00:00:00')
ON DUPLICATE KEY UPDATE email=email;

INSERT INTO wallet_account (id, user_id, balance, currency, account_number, status, created_at) VALUES
(1, 1, 500.00, 'USD', 'WAL-1001', 'active', '2024-01-15 10:05:00'),
(2, 2, 1200.00, 'USD', 'WAL-1002', 'active', '2024-01-20 11:35:00'),
(3, 3, 0.00, 'USD', 'WAL-1003', 'active', '2024-02-01 09:20:00'),
(4, 4, 10000.00, 'USD', 'WAL-2001', 'active', '2024-01-10 08:05:00'),
(5, 5, 7500.00, 'USD', 'WAL-2002', 'active', '2024-01-12 14:25:00'),
(6, 6, 1000.00, 'USD', 'WAL-0001', 'active', '2024-01-01 00:05:00')
ON DUPLICATE KEY UPDATE user_id=user_id;

INSERT INTO kyc_data (id, user_id, document_type, document_number, verification_status, verified_at, verified_by, created_at) VALUES
(1, 1, 'drivers_license', 'DL-NY-123456', 'approved', '2024-01-15 12:00:00', 6, '2024-01-15 10:30:00'),
(2, 2, 'passport', 'PP-USA-789012', 'approved', '2024-01-20 15:00:00', 6, '2024-01-20 12:00:00'),
(3, 3, 'drivers_license', 'DL-IL-345678', 'pending', NULL, NULL, '2024-02-01 10:00:00')
ON DUPLICATE KEY UPDATE user_id=user_id;

INSERT INTO loan_application (id, applicant_id, amount, purpose, term_months, interest_rate, status, reviewed_by, reviewed_at, created_at) VALUES
(1, 1, 5000.00, 'Business expansion', 12, 8.5, 'approved', 6, '2024-01-16 10:00:00', '2024-01-15 14:00:00'),
(2, 2, 10000.00, 'Home improvement', 24, 7.2, 'approved', 6, '2024-01-21 09:00:00', '2024-01-20 16:00:00'),
(3, 3, 3000.00, 'Debt consolidation', 12, 9.0, 'pending', NULL, NULL, '2024-02-01 11:00:00')
ON DUPLICATE KEY UPDATE applicant_id=applicant_id;

INSERT INTO loan (id, application_id, borrower_id, lender_id, principal_amount, interest_rate, term_months, monthly_payment, outstanding_balance, status, disbursed_at, maturity_date, created_at) VALUES
(1, 1, 1, 4, 5000.00, 8.5, 12, 434.58, 4500.00, 'active', '2024-01-16 14:00:00', '2025-01-16', '2024-01-16 11:00:00'),
(2, 2, 2, 5, 10000.00, 7.2, 24, 451.58, 9200.00, 'active', '2024-01-21 15:00:00', '2026-01-21', '2024-01-21 10:00:00')
ON DUPLICATE KEY UPDATE application_id=application_id;

INSERT INTO transaction_ledger (id, wallet_id, loan_id, transaction_type, amount, balance_before, balance_after, description, reference_number, created_at) VALUES
(1, 1, 1, 'loan_disbursement', 5000.00, 0.00, 5000.00, 'Loan disbursement', 'TXN-2024-0001', '2024-01-16 14:05:00'),
(2, 1, 1, 'loan_repayment', -434.58, 5000.00, 4565.42, 'Monthly payment 1', 'TXN-2024-0003', '2024-02-16 10:00:00'),
(3, 1, 1, 'loan_repayment', -434.58, 4565.42, 4130.84, 'Monthly payment 2', 'TXN-2024-0005', '2024-03-16 10:00:00'),
(4, 2, 2, 'loan_disbursement', 10000.00, 0.00, 10000.00, 'Loan disbursement', 'TXN-2024-0007', '2024-01-21 15:05:00'),
(5, 2, 2, 'loan_repayment', -451.58, 10000.00, 9548.42, 'Monthly payment 1', 'TXN-2024-0009', '2024-02-21 10:00:00')
ON DUPLICATE KEY UPDATE wallet_id=wallet_id;

INSERT INTO repayment_schedule (loan_id, installment_number, due_date, principal_amount, interest_amount, total_amount, paid_amount, paid_at, status) VALUES
(1, 1, '2024-02-16', 398.75, 35.83, 434.58, 434.58, '2024-02-16 10:00:00', 'paid'),
(1, 2, '2024-03-16', 401.58, 33.00, 434.58, 434.58, '2024-03-16 10:00:00', 'paid'),
(1, 3, '2024-04-16', 404.43, 30.15, 434.58, 0.00, NULL, 'pending'),
(2, 1, '2024-02-21', 391.58, 60.00, 451.58, 451.58, '2024-02-21 10:00:00', 'paid'),
(2, 2, '2024-03-21', 393.92, 57.66, 451.58, 0.00, NULL, 'pending')
ON DUPLICATE KEY UPDATE loan_id=loan_id;

INSERT INTO audit_log (user_id, action, table_name, record_id, new_values, ip_address, created_at) VALUES
(6, 'user_created', 'user', 1, '{"email":"john.doe@email.com","role":"borrower"}', '192.168.1.100', '2024-01-15 10:00:00'),
(6, 'loan_approved', 'loan_application', 1, '{"applicant_id":1,"amount":5000,"status":"approved"}', '192.168.1.100', '2024-01-16 10:00:00'),
(1, 'loan_disbursed', 'loan', 1, '{"borrower_id":1,"amount":5000}', '192.168.1.50', '2024-01-16 14:05:00')
ON DUPLICATE KEY UPDATE user_id=user_id;

-- =============================================================================
-- STORED PROCEDURES - REQUIREMENT 3
-- =============================================================================

DROP PROCEDURE IF EXISTS sp_apply_for_loan;
DROP PROCEDURE IF EXISTS sp_process_repayment;
DROP PROCEDURE IF EXISTS sp_calculate_risk_score;

DELIMITER //

-- Procedure 1: Apply for a loan
CREATE PROCEDURE sp_apply_for_loan(
    IN p_applicant_id INT,
    IN p_loan_amount DECIMAL(15,2),
    IN p_purpose TEXT,
    IN p_term_months INT
)
BEGIN
    DECLARE v_credit_score INT;
    DECLARE v_interest_rate DECIMAL(5,2);
    
    -- Error handling
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'Error: Loan application failed' AS error_message;
    END;
    
    START TRANSACTION;
    
    -- Get applicant's credit score
    SELECT credit_score INTO v_credit_score
    FROM user
    WHERE id = p_applicant_id;
    
    -- Calculate interest rate based on credit score
    SET v_interest_rate = CASE
        WHEN v_credit_score >= 750 THEN 5.0
        WHEN v_credit_score >= 650 THEN 8.0
        WHEN v_credit_score >= 550 THEN 12.0
        ELSE 15.0
    END;
    
    -- Insert loan application
    INSERT INTO loan_application (
        applicant_id, 
        amount, 
        purpose, 
        term_months,
        interest_rate,
        status
    ) VALUES (
        p_applicant_id,
        p_loan_amount,
        p_purpose,
        p_term_months,
        v_interest_rate,
        'pending'
    );
    
    COMMIT;
    SELECT LAST_INSERT_ID() AS application_id, 
           v_interest_rate AS suggested_interest_rate,
           'Application submitted successfully' AS message;
END //

-- Procedure 2: Process repayment
CREATE PROCEDURE sp_process_repayment(
    IN p_loan_id INT,
    IN p_payment_amount DECIMAL(15,2),
    IN p_borrower_wallet_id INT
)
BEGIN
    DECLARE v_outstanding DECIMAL(15,2);
    DECLARE v_borrower_balance DECIMAL(15,2);
    
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SELECT 'Error: Repayment failed' AS error_message;
    END;
    
    START TRANSACTION;
    
    -- Check borrower's wallet balance
    SELECT balance INTO v_borrower_balance
    FROM wallet_account
    WHERE id = p_borrower_wallet_id
    FOR UPDATE;
    
    IF v_borrower_balance < p_payment_amount THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Insufficient funds for repayment';
    END IF;
    
    -- Get outstanding balance
    SELECT outstanding_balance INTO v_outstanding
    FROM loan
    WHERE id = p_loan_id
    FOR UPDATE;
    
    -- Deduct from borrower's wallet
    UPDATE wallet_account
    SET balance = balance - p_payment_amount
    WHERE id = p_borrower_wallet_id;
    
    -- Update loan outstanding balance
    UPDATE loan
    SET outstanding_balance = outstanding_balance - p_payment_amount,
        status = CASE 
            WHEN (outstanding_balance - p_payment_amount) <= 0 THEN 'paid_off'
            ELSE status
        END
    WHERE id = p_loan_id;
    
    -- Create transaction record
    INSERT INTO transaction_ledger (
        from_wallet_id,
        to_wallet_id,
        amount,
        transaction_type,
        reference_id,
        status
    ) VALUES (
        p_borrower_wallet_id,
        NULL,
        p_payment_amount,
        'repayment',
        p_loan_id,
        'completed'
    );
    
    COMMIT;
    SELECT 'Repayment processed successfully' AS message, 
           (v_outstanding - p_payment_amount) AS remaining_balance;
END //

-- Procedure 3: Calculate comprehensive risk score
CREATE PROCEDURE sp_calculate_risk_score(
    IN p_user_id INT,
    IN p_loan_amount DECIMAL(15,2),
    OUT p_risk_score DECIMAL(5,2),
    OUT p_risk_category VARCHAR(20)
)
BEGIN
    DECLARE v_credit_score INT;
    DECLARE v_active_loans INT;
    DECLARE v_total_borrowed DECIMAL(15,2);
    DECLARE v_payment_history INT;
    
    -- Get user's credit score
    SELECT credit_score INTO v_credit_score
    FROM user
    WHERE id = p_user_id;
    
    -- Count active loans
    SELECT COUNT(*) INTO v_active_loans
    FROM loan
    WHERE borrower_id = p_user_id AND status = 'active';
    
    -- Total currently borrowed
    SELECT COALESCE(SUM(outstanding_balance), 0) INTO v_total_borrowed
    FROM loan
    WHERE borrower_id = p_user_id AND status = 'active';
    
    -- Payment history (count on-time payments)
    SELECT COUNT(*) INTO v_payment_history
    FROM repayment_schedule
    WHERE loan_id IN (SELECT id FROM loan WHERE borrower_id = p_user_id)
    AND status = 'paid';
    
    -- Calculate risk score (0-100, higher = riskier)
    SET p_risk_score = 
        -- Credit score factor (0-40 points)
        (CASE
            WHEN v_credit_score >= 750 THEN 10
            WHEN v_credit_score >= 650 THEN 20
            WHEN v_credit_score >= 550 THEN 30
            ELSE 40
        END) +
        -- Existing loans factor (0-30 points)
        (CASE
            WHEN v_active_loans = 0 THEN 5
            WHEN v_active_loans <= 2 THEN 15
            ELSE 30
        END) +
        -- Debt-to-loan ratio (0-30 points)
        (CASE
            WHEN v_total_borrowed = 0 THEN 5
            WHEN (v_total_borrowed / p_loan_amount) < 2 THEN 15
            ELSE 30
        END);
    
    -- Categorize risk
    SET p_risk_category = CASE
        WHEN p_risk_score <= 30 THEN 'Low Risk'
        WHEN p_risk_score <= 60 THEN 'Medium Risk'
        ELSE 'High Risk'
    END;
END //

DELIMITER ;


-- =============================================================================
-- VIEWS - REQUIREMENT 4
-- =============================================================================

-- View 1: Simple view - Active loans
CREATE OR REPLACE VIEW v_active_loans AS
SELECT 
    l.id AS loan_id,
    l.principal_amount,
    l.interest_rate,
    l.outstanding_balance,
    l.status,
    l.disbursed_at,
    l.maturity_date,
    b.full_name AS borrower_name,
    b.email AS borrower_email,
    le.full_name AS lender_name
FROM loan l
JOIN user b ON l.borrower_id = b.id
LEFT JOIN user le ON l.lender_id = le.id
WHERE l.status = 'active';

-- View 2: Complex view - Portfolio dashboard with aggregations
CREATE OR REPLACE VIEW v_portfolio_dashboard AS
SELECT 
    u.id AS user_id,
    u.full_name,
    u.email,
    u.role,
    u.credit_score,
    w.balance AS wallet_balance,
    -- Lending metrics (for lenders)
    COALESCE(lender_stats.loans_funded, 0) AS loans_funded,
    COALESCE(lender_stats.total_funded, 0) AS total_amount_lent,
    COALESCE(lender_stats.active_investments, 0) AS active_investments,
    COALESCE(lender_stats.total_outstanding, 0) AS outstanding_receivables,
    -- Borrowing metrics (for borrowers)
    COALESCE(borrower_stats.loans_taken, 0) AS loans_taken,
    COALESCE(borrower_stats.total_borrowed, 0) AS total_amount_borrowed,
    COALESCE(borrower_stats.active_loans, 0) AS active_loans,
    COALESCE(borrower_stats.total_owed, 0) AS total_amount_owed,
    -- Calculated metrics
    CASE 
        WHEN u.role = 'lender' THEN 
            ROUND((COALESCE(lender_stats.total_outstanding, 0) / NULLIF(COALESCE(lender_stats.total_funded, 0), 0)) * 100, 2)
        ELSE NULL
    END AS portfolio_at_risk_pct,
    CASE
        WHEN u.role = 'borrower' THEN
            ROUND((COALESCE(borrower_stats.total_owed, 0) / NULLIF(w.balance, 0)) * 100, 2)
        ELSE NULL
    END AS debt_to_wallet_ratio
FROM user u
LEFT JOIN wallet_account w ON u.id = w.user_id
LEFT JOIN (
    -- Lender statistics
    SELECT 
        lender_id,
        COUNT(*) AS loans_funded,
        SUM(principal_amount) AS total_funded,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_investments,
        SUM(CASE WHEN status = 'active' THEN outstanding_balance ELSE 0 END) AS total_outstanding
    FROM loan
    WHERE lender_id IS NOT NULL
    GROUP BY lender_id
) lender_stats ON u.id = lender_stats.lender_id
LEFT JOIN (
    -- Borrower statistics
    SELECT 
        borrower_id,
        COUNT(*) AS loans_taken,
        SUM(principal_amount) AS total_borrowed,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_loans,
        SUM(CASE WHEN status = 'active' THEN outstanding_balance ELSE 0 END) AS total_owed
    FROM loan
    GROUP BY borrower_id
) borrower_stats ON u.id = borrower_stats.borrower_id;

-- View 3: Security view - User profile without sensitive data
CREATE OR REPLACE VIEW v_user_profile_safe AS
SELECT 
    id,
    email,
    full_name,
    role,
    phone,
    LEFT(address, 20) AS address_preview,  -- Only show first 20 chars
    CASE 
        WHEN credit_score >= 750 THEN 'Excellent'
        WHEN credit_score >= 650 THEN 'Good'
        WHEN credit_score >= 550 THEN 'Fair'
        ELSE 'Poor'
    END AS credit_rating,
    is_active,
    created_at
FROM user;


-- =============================================================================
-- AUDIT TRIGGERS - REQUIREMENT 7
-- =============================================================================

DROP TRIGGER IF EXISTS trg_user_before_insert;
DROP TRIGGER IF EXISTS trg_user_after_insert;
DROP TRIGGER IF EXISTS trg_loan_after_update;
DROP TRIGGER IF EXISTS trg_wallet_after_update;

DELIMITER //

-- Trigger 1: BEFORE INSERT on user - validate and format data
CREATE TRIGGER trg_user_before_insert
BEFORE INSERT ON user
FOR EACH ROW
BEGIN
    -- Validate email format
    IF NEW.email NOT LIKE '%_@__%.__%' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Invalid email format';
    END IF;
    
    -- Validate credit score range
    IF NEW.credit_score IS NOT NULL AND (NEW.credit_score < 300 OR NEW.credit_score > 850) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Credit score must be between 300 and 850';
    END IF;
    
    -- Normalize email to lowercase
    SET NEW.email = LOWER(NEW.email);
    
    -- Normalize role
    SET NEW.role = LOWER(NEW.role);
END //

-- Trigger 2: AFTER INSERT on user - audit log
CREATE TRIGGER trg_user_after_insert
AFTER INSERT ON user
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (
        table_name,
        record_id,
        action,
        user_id,
        new_values
    ) VALUES (
        'user',
        NEW.id,
        'INSERT',
        NEW.id,
        JSON_OBJECT(
            'email', NEW.email,
            'full_name', NEW.full_name,
            'role', NEW.role,
            'credit_score', NEW.credit_score
        )
    );
END //

-- Trigger 3: AFTER UPDATE on loan - audit status changes
CREATE TRIGGER trg_loan_after_update
AFTER UPDATE ON loan
FOR EACH ROW
BEGIN
    IF OLD.status != NEW.status OR OLD.outstanding_balance != NEW.outstanding_balance THEN
        INSERT INTO audit_log (
            table_name,
            record_id,
            action,
            user_id,
            old_values,
            new_values
        ) VALUES (
            'loan',
            NEW.id,
            'UPDATE',
            NEW.borrower_id,
            JSON_OBJECT(
                'status', OLD.status,
                'outstanding_balance', OLD.outstanding_balance
            ),
            JSON_OBJECT(
                'status', NEW.status,
                'outstanding_balance', NEW.outstanding_balance
            )
        );
    END IF;
END //

-- Trigger 4: AFTER UPDATE on wallet_account - audit balance changes
CREATE TRIGGER trg_wallet_after_update
AFTER UPDATE ON wallet_account
FOR EACH ROW
BEGIN
    IF OLD.balance != NEW.balance THEN
        INSERT INTO audit_log (
            table_name,
            record_id,
            action,
            user_id,
            old_values,
            new_values
        ) VALUES (
            'wallet_account',
            NEW.id,
            'UPDATE',
            NEW.user_id,
            JSON_OBJECT('balance', OLD.balance),
            JSON_OBJECT('balance', NEW.balance)
        );
    END IF;
END //

DELIMITER ;


-- =============================================================================
-- USER ACCESS CONTROL - REQUIREMENT 2
-- =============================================================================

-- Create MySQL roles for different access levels
CREATE ROLE IF NOT EXISTS 'db_admin'@'%';
CREATE ROLE IF NOT EXISTS 'app_user'@'%';
CREATE ROLE IF NOT EXISTS 'read_only_analyst'@'%';

-- ADMIN ROLE: Full DDL and DML access
GRANT ALL PRIVILEGES ON microlending.* TO 'db_admin'@'%';

-- APP USER ROLE: DML only on specific tables (no DDL)
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.user TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.wallet_account TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.loan_application TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.loan TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.transaction_ledger TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON microlending.repayment_schedule TO 'app_user'@'%';
GRANT SELECT, INSERT, UPDATE ON microlending.kyc_data TO 'app_user'@'%';
GRANT SELECT, INSERT ON microlending.audit_log TO 'app_user'@'%';

-- READ-ONLY ROLE: SELECT only
GRANT SELECT ON microlending.user TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.wallet_account TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.loan_application TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.loan TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.transaction_ledger TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.repayment_schedule TO 'read_only_analyst'@'%';
GRANT SELECT ON microlending.audit_log TO 'read_only_analyst'@'%';

-- Create test users assigned to roles
CREATE USER IF NOT EXISTS 'admin_user'@'%' IDENTIFIED BY 'admin123';
CREATE USER IF NOT EXISTS 'app_backend'@'%' IDENTIFIED BY 'app123';
CREATE USER IF NOT EXISTS 'analyst_user'@'%' IDENTIFIED BY 'analyst123';

-- Grant roles to users
GRANT 'db_admin'@'%' TO 'admin_user'@'%';
GRANT 'app_user'@'%' TO 'app_backend'@'%';
GRANT 'read_only_analyst'@'%' TO 'analyst_user'@'%';

-- Set default roles (active on login)
SET DEFAULT ROLE 'db_admin'@'%' TO 'admin_user'@'%';
SET DEFAULT ROLE 'app_user'@'%' TO 'app_backend'@'%';
SET DEFAULT ROLE 'read_only_analyst'@'%' TO 'analyst_user'@'%';

-- HOW TO TEST:
-- 1. View grants: SHOW GRANTS FOR 'db_admin'@'%';
-- 2. Connect as admin: mysql -h <host> -u admin_user -padmin123 microlending
-- 3. Connect as app: mysql -h <host> -u app_backend -papp123 microlending
-- 4. Connect as analyst: mysql -h <host> -u analyst_user -panalyst123 microlending
-- 5. REVOKE demo: REVOKE INSERT ON microlending.audit_log FROM 'app_user'@'%';

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT '✓ Schema created successfully' as status;
SELECT COUNT(*) as user_count FROM user;
SELECT COUNT(*) as wallet_count FROM wallet_account;
SELECT COUNT(*) as loan_count FROM loan;
SELECT '✓ Demo data loaded' as status;
SELECT '✓ Login with: john.doe@email.com / password123' as credentials;
