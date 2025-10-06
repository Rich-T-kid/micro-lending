-- Users & Roles
CREATE TABLE IF NOT EXISTS user_account (
user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
name_first VARCHAR(80) NOT NULL,
name_last VARCHAR(80) NOT NULL,
email VARCHAR(255) NOT NULL UNIQUE,
phone VARCHAR(32) UNIQUE,
date_of_birth DATE,
status ENUM('active','suspended','closed') DEFAULT 'active',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role (
role_id TINYINT PRIMARY KEY,
role_name ENUM('BORROWER','LENDER','ADMIN') UNIQUE
);

CREATE TABLE IF NOT EXISTS user_role (
user_id BIGINT NOT NULL,
role_id TINYINT NOT NULL,
assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY (user_id, role_id),
FOREIGN KEY (user_id) REFERENCES user_account(user_id),
FOREIGN KEY (role_id) REFERENCES role(role_id)
);

/*--(Know Your Customer) KYC*/
CREATE TABLE IF NOT EXISTS identity_kyc (
kyc_id BIGINT PRIMARY KEY AUTO_INCREMENT,
user_id BIGINT NOT NULL UNIQUE,
government_id_type VARCHAR(32),
government_id_hash VARBINARY(64),
address_line1 VARCHAR(120),
address_line2 VARCHAR(120),
city VARCHAR(80), state VARCHAR(80), postal_code VARCHAR(20), country VARCHAR(2),
status ENUM('pending','verified','failed') DEFAULT 'pending',
verified_at TIMESTAMP NULL,
FOREIGN KEY (user_id) REFERENCES user_account(user_id)
);

-- Institutions
CREATE TABLE IF NOT EXISTS institution (
institution_id BIGINT PRIMARY KEY AUTO_INCREMENT,
legal_name VARCHAR(255) NOT NULL UNIQUE,
type ENUM('BANK','CREDIT_UNION','NGO','OTHER') NOT NULL,
contact_email VARCHAR(255),
contact_phone VARCHAR(32),
status ENUM('active','suspended','closed') DEFAULT 'active',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Currency & Accounts
CREATE TABLE IF NOT EXISTS currency (
currency_code CHAR(3) PRIMARY KEY,
name VARCHAR(64),
decimals TINYINT NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS wallet_account (
account_id BIGINT PRIMARY KEY AUTO_INCREMENT,
owner_type ENUM('USER','INSTITUTION') NOT NULL,
owner_id BIGINT NOT NULL,
currency_code CHAR(3) NOT NULL,
available_balance DECIMAL(18,4) NOT NULL DEFAULT 0,
hold_balance DECIMAL(18,4) NOT NULL DEFAULT 0,
status ENUM('active','frozen','closed') DEFAULT 'active',
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (currency_code) REFERENCES currency(currency_code),
INDEX idx_owner (owner_type, owner_id)
);

-- Applications & Risk
CREATE TABLE IF NOT EXISTS loan_application (
app_id BIGINT PRIMARY KEY AUTO_INCREMENT,
applicant_id BIGINT NOT NULL,
channel ENUM('P2P','INSTITUTION') NOT NULL,
target_institution_id BIGINT NULL,
requested_amount DECIMAL(18,2) NOT NULL,
currency_code CHAR(3) NOT NULL,
purpose VARCHAR(255),
term_months SMALLINT NOT NULL,
collateral_flag BOOLEAN DEFAULT FALSE,
notes TEXT,
status ENUM('DRAFT','SUBMITTED','ASSESSING','OPEN_FOR_OFFERS','APPROVED','REJECTED','WITHDRAWN') NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (applicant_id) REFERENCES user_account(user_id),
FOREIGN KEY (target_institution_id) REFERENCES institution(institution_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

CREATE TABLE IF NOT EXISTS risk_assessment (
risk_id BIGINT PRIMARY KEY AUTO_INCREMENT,
app_id BIGINT NOT NULL UNIQUE,
model_version VARCHAR(32) NOT NULL,
score_numeric INT NOT NULL,
risk_band ENUM('A','B','C','D','E') NOT NULL,
dti_ratio DECIMAL(6,3),
income_verified BOOLEAN DEFAULT FALSE,
recommendation ENUM('APPROVE','REVIEW','DECLINE') NOT NULL,
assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (app_id) REFERENCES loan_application(app_id)
);

-- Offers & Loans
CREATE TABLE IF NOT EXISTS loan_offer (
offer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
app_id BIGINT NOT NULL,
lender_type ENUM('USER','INSTITUTION') NOT NULL,
lender_id BIGINT NOT NULL,
principal_amount DECIMAL(18,2) NOT NULL,
currency_code CHAR(3) NOT NULL,
interest_rate_apr DECIMAL(6,3) NOT NULL,
repayment_type ENUM('AMORTIZING','INTEREST_ONLY','BULLET') NOT NULL,
term_months SMALLINT NOT NULL,
grace_period_days SMALLINT DEFAULT 0,
fees_flat DECIMAL(18,2) DEFAULT 0,
fees_percent DECIMAL(5,3) DEFAULT 0,
conditions_text TEXT,
status ENUM('PENDING','ACCEPTED','WITHDRAWN','EXPIRED','REJECTED') NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (app_id) REFERENCES loan_application(app_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code),
INDEX idx_lender (lender_type, lender_id)
);

CREATE TABLE IF NOT EXISTS loan (
loan_id BIGINT PRIMARY KEY AUTO_INCREMENT,
app_id BIGINT NOT NULL UNIQUE,
offer_id BIGINT NOT NULL UNIQUE,
borrower_id BIGINT NOT NULL,
lender_type ENUM('USER','INSTITUTION') NOT NULL,
lender_id BIGINT NOT NULL,
principal_amount DECIMAL(18,2) NOT NULL,
currency_code CHAR(3) NOT NULL,
interest_rate_apr DECIMAL(6,3) NOT NULL,
origination_fee DECIMAL(18,2) DEFAULT 0,
start_date DATE NOT NULL,
maturity_date DATE NOT NULL,
status ENUM('ACTIVE','CLOSED','DEFAULTED','CHARGED_OFF') NOT NULL,
FOREIGN KEY (app_id) REFERENCES loan_application(app_id),
FOREIGN KEY (offer_id) REFERENCES loan_offer(offer_id),
FOREIGN KEY (borrower_id) REFERENCES user_account(user_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

-- Schedules & Payments
CREATE TABLE IF NOT EXISTS repayment_schedule (
schedule_id BIGINT PRIMARY KEY AUTO_INCREMENT,
loan_id BIGINT NOT NULL,
installment_no INT NOT NULL,
due_date DATE NOT NULL,
due_principal DECIMAL(18,2) NOT NULL DEFAULT 0,
due_interest DECIMAL(18,2) NOT NULL DEFAULT 0,
due_fees DECIMAL(18,2) NOT NULL DEFAULT 0,
status ENUM('PENDING','PARTIAL','PAID','LATE','WAIVED') DEFAULT 'PENDING',
paid_at TIMESTAMP NULL,
UNIQUE (loan_id, installment_no),
FOREIGN KEY (loan_id) REFERENCES loan(loan_id)
);

CREATE TABLE IF NOT EXISTS disbursement (
disb_id BIGINT PRIMARY KEY AUTO_INCREMENT,
loan_id BIGINT NOT NULL,
from_account_id BIGINT NOT NULL,
to_account_id BIGINT NOT NULL,
amount DECIMAL(18,2) NOT NULL,
currency_code CHAR(3) NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
status ENUM('PENDING','POSTED','FAILED') DEFAULT 'PENDING',
FOREIGN KEY (loan_id) REFERENCES loan(loan_id),
FOREIGN KEY (from_account_id) REFERENCES wallet_account(account_id),
FOREIGN KEY (to_account_id) REFERENCES wallet_account(account_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

CREATE TABLE IF NOT EXISTS repayment (
pay_id BIGINT PRIMARY KEY AUTO_INCREMENT,
loan_id BIGINT NOT NULL,
from_account_id BIGINT NOT NULL,
to_account_id BIGINT NOT NULL,
amount DECIMAL(18,2) NOT NULL,
currency_code CHAR(3) NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
status ENUM('PENDING','POSTED','FAILED') DEFAULT 'PENDING',
FOREIGN KEY (loan_id) REFERENCES loan(loan_id),
FOREIGN KEY (from_account_id) REFERENCES wallet_account(account_id),
FOREIGN KEY (to_account_id) REFERENCES wallet_account(account_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

CREATE TABLE IF NOT EXISTS repayment_allocation (
allocation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
pay_id BIGINT NOT NULL,
schedule_id BIGINT NOT NULL,
to_principal DECIMAL(18,2) NOT NULL DEFAULT 0,
to_interest DECIMAL(18,2) NOT NULL DEFAULT 0,
to_fees DECIMAL(18,2) NOT NULL DEFAULT 0,
FOREIGN KEY (pay_id) REFERENCES repayment(pay_id),
FOREIGN KEY (schedule_id) REFERENCES repayment_schedule(schedule_id)
);

-- Ledger
CREATE TABLE IF NOT EXISTS transaction_ledger (
tx_id BIGINT PRIMARY KEY AUTO_INCREMENT,
related_type ENUM('DISBURSEMENT','REPAYMENT','FEE','ADJUSTMENT','REVERSAL') NOT NULL,
related_id BIGINT NULL,
account_id BIGINT NOT NULL,
direction ENUM('DEBIT','CREDIT') NOT NULL,
amount DECIMAL(18,4) NOT NULL,
currency_code CHAR(3) NOT NULL,
memo VARCHAR(255),
posted_by BIGINT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (account_id) REFERENCES wallet_account(account_id),
FOREIGN KEY (posted_by) REFERENCES user_account(user_id),
FOREIGN KEY (currency_code) REFERENCES currency(currency_code)
);

-- Delinquency & Oversight
CREATE TABLE IF NOT EXISTS delinquency_report (
dr_id BIGINT PRIMARY KEY AUTO_INCREMENT,
loan_id BIGINT NOT NULL,
days_past_due INT NOT NULL,
snapshot_date DATE NOT NULL,
status ENUM('CURRENT','DPD_30','DPD_60','DPD_90','DEFAULT') NOT NULL,
FOREIGN KEY (loan_id) REFERENCES loan(loan_id),
UNIQUE (loan_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS message_thread (
thread_id BIGINT PRIMARY KEY AUTO_INCREMENT,
app_id BIGINT NOT NULL,
created_by BIGINT NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (app_id) REFERENCES loan_application(app_id),
FOREIGN KEY (created_by) REFERENCES user_account(user_id)
);

CREATE TABLE IF NOT EXISTS message (
message_id BIGINT PRIMARY KEY AUTO_INCREMENT,
thread_id BIGINT NOT NULL,
sender_type ENUM('USER','INSTITUTION','ADMIN') NOT NULL,
sender_id BIGINT NOT NULL,
body_text TEXT NOT NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (thread_id) REFERENCES message_thread(thread_id)
);

CREATE TABLE IF NOT EXISTS rating_review (
review_id BIGINT PRIMARY KEY AUTO_INCREMENT,
reviewer_id BIGINT NOT NULL,
reviewee_id BIGINT NOT NULL,
rating TINYINT NOT NULL,
comment TEXT,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
UNIQUE (reviewer_id, reviewee_id),
FOREIGN KEY (reviewer_id) REFERENCES user_account(user_id),
FOREIGN KEY (reviewee_id) REFERENCES user_account(user_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
audit_id BIGINT PRIMARY KEY AUTO_INCREMENT,
actor_id BIGINT NULL,
action VARCHAR(64) NOT NULL,
entity_type VARCHAR(64) NOT NULL,
entity_id BIGINT NOT NULL,
old_values_json JSON NULL,
new_values_json JSON NULL,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (actor_id) REFERENCES user_account(user_id)
);
