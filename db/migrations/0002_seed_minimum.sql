-- 0002_seed_minimum.sql
-- Seed baseline reference data for roles and currencies.

SET NAMES utf8mb4;
SET time_zone = '+00:00';
-- ==========================================================
INSERT INTO role (role_id, role_name) VALUES
  (1, 'BORROWER'),
  (2, 'LENDER'),
  (3, 'ADMIN')
ON DUPLICATE KEY UPDATE
  role_name = VALUES(role_name);
-- ==========================================================
INSERT INTO currency (currency_code, name, decimals) VALUES
  ('USD', 'US Dollar', 2),
  ('EUR', 'Euro', 2),
  ('GBP', 'British Pound', 2),
  ('JPY', 'Japanese Yen', 0),
  ('MXN', 'Mexican Peso', 2),
  ('CAD', 'Canadian Dollar', 2),
  ('INR', 'Indian Rupee', 2)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  decimals = VALUES(decimals);
