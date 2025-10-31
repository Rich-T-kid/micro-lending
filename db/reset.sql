-- =============================================================================
-- DATABASE RESET SCRIPT
-- =============================================================================
-- Use this ONLY when you need to completely reset the database
-- This drops all existing tables and recreates from schema.sql
-- 
-- WARNING: This will DELETE ALL DATA
-- 
-- Usage: mysql -h <host> -u admin -p microlending < reset.sql
-- =============================================================================

USE microlending;

SET FOREIGN_KEY_CHECKS = 0;

-- Drop all tables
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS repayment_schedule;
DROP TABLE IF EXISTS transaction_ledger;
DROP TABLE IF EXISTS loan;
DROP TABLE IF EXISTS loan_application;
DROP TABLE IF EXISTS kyc_data;
DROP TABLE IF EXISTS wallet_account;
DROP TABLE IF EXISTS user;

-- Drop any old schema tables if they exist
DROP TABLE IF EXISTS message;
DROP TABLE IF EXISTS loan_offer;
DROP TABLE IF EXISTS risk_assessment;
DROP TABLE IF EXISTS identity_kyc;
DROP TABLE IF EXISTS identity_kyc_backup;
DROP TABLE IF EXISTS user_role;
DROP TABLE IF EXISTS role;
DROP TABLE IF EXISTS institution;
DROP TABLE IF EXISTS currency;
DROP TABLE IF EXISTS user_account;

SET FOREIGN_KEY_CHECKS = 1;

SELECT '✓ All tables dropped' as status;
SELECT '✓ Now run: mysql ... < schema.sql' as next_step;
