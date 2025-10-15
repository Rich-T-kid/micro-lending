-- 0003_indexes.sql (MySQL 8 compatible)
-- Creates indexes only if missing; also defines reporting views.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- Recreate helper proc safely
DROP PROCEDURE IF EXISTS add_index_if_missing;

DELIMITER $$
CREATE PROCEDURE add_index_if_missing(
  IN p_table   VARCHAR(64),
  IN p_index   VARCHAR(64),
  IN p_columns VARCHAR(512)
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = p_table
      AND INDEX_NAME   = p_index
  ) THEN
    SET @sql = CONCAT('CREATE INDEX ', p_index, ' ON ', p_table, ' (', p_columns, ')');
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$
DELIMITER ;

-- =========================
-- Indexes
-- =========================

CALL add_index_if_missing('user_account',       'idx_user_account_email',          'email');
CALL add_index_if_missing('user_account',       'idx_user_account_status_created', 'status, created_at');

CALL add_index_if_missing('user_role',          'idx_user_role_role',              'role_id, assigned_at');

CALL add_index_if_missing('identity_kyc',       'idx_kyc_user',                    'user_id');
CALL add_index_if_missing('identity_kyc',       'idx_kyc_status',                  'status, verified_at');

CALL add_index_if_missing('institution',        'idx_institution_status',          'status, created_at');

CALL add_index_if_missing('wallet_account',     'idx_wallet_currency',             'currency_code');
CALL add_index_if_missing('wallet_account',     'idx_wallet_status',               'status, created_at');

CALL add_index_if_missing('loan_application',   'idx_applicant',                   'applicant_id, created_at');
CALL add_index_if_missing('loan_application',   'idx_app_status',                  'status, created_at');
CALL add_index_if_missing('loan_application',   'idx_app_institution',             'target_institution_id, created_at');
CALL add_index_if_missing('loan_application',   'idx_app_channel',                 'channel, created_at');
CALL add_index_if_missing('loan_application',   'idx_app_currency',                'currency_code');

CALL add_index_if_missing('risk_assessment',    'idx_risk_app_unique',             'app_id');            -- uniqueness by table def
CALL add_index_if_missing('risk_assessment',    'idx_risk_score',                  'risk_band, score_numeric');

CALL add_index_if_missing('loan_offer',         'idx_offer_app',                   'app_id, created_at');
CALL add_index_if_missing('loan_offer',         'idx_offer_status',                'status, created_at');
CALL add_index_if_missing('loan_offer',         'idx_offer_lender',                'lender_type, lender_id');
CALL add_index_if_missing('loan_offer',         'idx_offer_currency',              'currency_code');

CALL add_index_if_missing('loan',               'idx_loan_app_unique',             'app_id');            -- uniqueness by table def
CALL add_index_if_missing('loan',               'idx_loan_offer_unique',           'offer_id');          -- uniqueness by table def
CALL add_index_if_missing('loan',               'idx_loan_borrower',               'borrower_id, status');
CALL add_index_if_missing('loan',               'idx_loan_lender',                 'lender_type, lender_id, status');
CALL add_index_if_missing('loan',               'idx_loan_dates',                  'start_date, maturity_date');
CALL add_index_if_missing('loan',               'idx_loan_currency',               'currency_code');

CALL add_index_if_missing('repayment_schedule', 'idx_sched_unique_installment',    'loan_id, installment_no');
CALL add_index_if_missing('repayment_schedule', 'idx_sched_due',                   'loan_id, due_date');
CALL add_index_if_missing('repayment_schedule', 'idx_sched_status',                'status, due_date');

CALL add_index_if_missing('disbursement',       'idx_disb_loan',                   'loan_id, created_at');
CALL add_index_if_missing('disbursement',       'idx_disb_accounts',               'from_account_id, to_account_id');
CALL add_index_if_missing('disbursement',       'idx_disb_status',                 'status');
CALL add_index_if_missing('disbursement',       'idx_disb_currency',               'currency_code');

CALL add_index_if_missing('repayment',          'idx_pay_loan',                    'loan_id, created_at');
CALL add_index_if_missing('repayment',          'idx_pay_accounts',                'from_account_id, to_account_id');
CALL add_index_if_missing('repayment',          'idx_pay_status',                  'status');
CALL add_index_if_missing('repayment',          'idx_pay_currency',                'currency_code');

CALL add_index_if_missing('repayment_allocation','idx_alloc_pay',                  'pay_id');
CALL add_index_if_missing('repayment_allocation','idx_alloc_schedule',             'schedule_id');

CALL add_index_if_missing('transaction_ledger', 'idx_ledger_account_time',         'account_id, created_at');
CALL add_index_if_missing('transaction_ledger', 'idx_ledger_related',              'related_type, related_id');
CALL add_index_if_missing('transaction_ledger', 'idx_ledger_currency',             'currency_code');

CALL add_index_if_missing('delinquency_report', 'idx_delinquency_unique',          'loan_id, snapshot_date');
CALL add_index_if_missing('delinquency_report', 'idx_delinquency_status',          'status, days_past_due');

CALL add_index_if_missing('message_thread',     'idx_thread_app',                  'app_id');
CALL add_index_if_missing('message_thread',     'idx_thread_creator',              'created_by, created_at');

CALL add_index_if_missing('message',            'idx_message_thread_time',         'thread_id, created_at');

CALL add_index_if_missing('rating_review',      'idx_rating_unique_pair',          'reviewer_id, reviewee_id');
CALL add_index_if_missing('rating_review',      'idx_rating_reviewee_time',        'reviewee_id, created_at');

CALL add_index_if_missing('audit_log',          'idx_audit_entity',                'entity_type, entity_id');
CALL add_index_if_missing('audit_log',          'idx_audit_actor_time',            'actor_id, created_at');

-- Clean up helper
DROP PROCEDURE IF EXISTS add_index_if_missing;

-- =========================
-- Reporting / Helper Views
-- =========================

CREATE OR REPLACE VIEW v_application_offers AS
SELECT
  a.app_id,
  a.applicant_id,
  a.channel,
  a.target_institution_id,
  a.requested_amount,
  a.currency_code,
  a.status AS application_status,
  a.created_at AS application_created_at,
  COALESCE(SUM(o.principal_amount), 0) AS committed_offers_amount,
  COALESCE(SUM(CASE WHEN o.status = 'ACCEPTED' THEN o.principal_amount ELSE 0 END), 0) AS accepted_offer_amount,
  COUNT(o.offer_id) AS offer_count
FROM loan_application a
LEFT JOIN loan_offer o ON o.app_id = a.app_id
GROUP BY
  a.app_id, a.applicant_id, a.channel, a.target_institution_id,
  a.requested_amount, a.currency_code, a.status, a.created_at;

CREATE OR REPLACE VIEW v_overdue_installments AS
SELECT
  s.schedule_id,
  s.loan_id,
  s.installment_no,
  s.due_date,
  s.due_principal,
  s.due_interest,
  s.due_fees,
  s.status,
  GREATEST(DATEDIFF(CURDATE(), s.due_date), 0) AS days_overdue
FROM repayment_schedule s
WHERE s.status IN ('PENDING','PARTIAL','LATE')
  AND s.due_date < CURDATE();

CREATE OR REPLACE VIEW v_loan_cash_flows AS
SELECT
  l.loan_id,
  l.borrower_id,
  l.lender_type,
  l.lender_id,
  l.currency_code,
  COALESCE(d.total_disbursed, 0) AS total_disbursed,
  COALESCE(r.total_repaid, 0)     AS total_repaid,
  COALESCE(d.total_disbursed, 0) - COALESCE(r.total_repaid, 0) AS net_outstanding
FROM loan l
LEFT JOIN (
  SELECT loan_id, SUM(amount) AS total_disbursed
  FROM disbursement
  WHERE status = 'POSTED'
  GROUP BY loan_id
) d ON d.loan_id = l.loan_id
LEFT JOIN (
  SELECT loan_id, SUM(amount) AS total_repaid
  FROM repayment
  WHERE status = 'POSTED'
  GROUP BY loan_id
) r ON r.loan_id = l.loan_id;

CREATE OR REPLACE VIEW v_loan_delinquency AS
SELECT
  l.loan_id,
  l.status AS loan_status,
  dr.status AS delinquency_status,
  dr.days_past_due,
  dr.snapshot_date
FROM loan l
LEFT JOIN (
  SELECT d1.*
  FROM delinquency_report d1
  JOIN (
    SELECT loan_id, MAX(snapshot_date) AS max_date
    FROM delinquency_report
    GROUP BY loan_id
  ) d2
    ON d1.loan_id = d2.loan_id AND d1.snapshot_date = d2.max_date
) dr
  ON dr.loan_id = l.loan_id;

-- Latest message per thread
CREATE OR REPLACE VIEW v_thread_latest_message AS
SELECT
  t.thread_id,
  t.app_id,
  t.created_by,
  t.created_at AS thread_created_at,
  (
    SELECT m1.message_id
    FROM message m1
    WHERE m1.thread_id = t.thread_id
    ORDER BY m1.created_at DESC, m1.message_id DESC
    LIMIT 1
  ) AS latest_message_id,
  (
    SELECT m1.sender_type
    FROM message m1
    WHERE m1.thread_id = t.thread_id
    ORDER BY m1.created_at DESC, m1.message_id DESC
    LIMIT 1
  ) AS latest_sender_type,
  (
    SELECT m1.sender_id
    FROM message m1
    WHERE m1.thread_id = t.thread_id
    ORDER BY m1.created_at DESC, m1.message_id DESC
    LIMIT 1
  ) AS latest_sender_id,
  (
    SELECT m1.created_at
    FROM message m1
    WHERE m1.thread_id = t.thread_id
    ORDER BY m1.created_at DESC, m1.message_id DESC
    LIMIT 1
  ) AS latest_message_at
FROM message_thread t;
