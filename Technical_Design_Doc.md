# Techinical Design Document (TDD)



## 1. Document Control
- **Version:** 1.0
- **Author:** Richard Baah, Jose Lamela, Saksham Mehta
- **Date:** 2025-9-4
- **Reviewers:** Dev Team
## 2. Introduction
This document describes the technical implementation for a microlending service. Linked FRD: [Micro-lending FRD](./Fuctional_Req.md)
## 3. High-Level Architecture
Link to: 
[Architectural Diagram](./Archietecural_Diagram.md)
### 4.1 Data Model
**tables**
- UserAccount(user_id, email, password_hash, full_name, phone, created_at, status)
- UserRole(role_id, role_name, description)
- UserAccountRole(user_id, role_id, assigned_at)
- Institution(institution_id, name, type, registration_no, contact_email, contact_phone, address, created_at, status)
- UserProfile(user_id, date_of_birth, country, address, credit_score, income, employment_status)
- KYCVerification(kyc_id, user_id, status, verified_at, data_json)
- Currency(currency_code, name, symbol, minor_unit)
- ExchangeRate(rate_id, base_currency, quote_currency, rate, as_of)
- Wallet(wallet_id, owner_type, owner_id, currency_code, balance, updated_at)
- Transaction(transaction_id, wallet_id, loan_id, type, amount, currency_code, occurred_at, reference, metadata_json)
- LoanProduct(product_id, institution_id, name, description, min_amount, max_amount, interest_rate_type, base_rate_apr, term_min_months, term_max_months, fees_json, collateral_required, created_at, status)
- LoanApplication(application_id, applicant_type, applicant_id, product_id, requested_amount, currency_code, requested_term_months, purpose, submitted_at, status, score, decisioned_at)
- UnderwritingRule(rule_id, name, description, rule_logic_json, active)
- UnderwritingDecision(decision_id, application_id, rule_id, outcome, score_delta, reasons_json, decided_at)
- P2PLoanRequest(request_id, borrower_id, requested_amount, currency_code, requested_term_months, purpose, posted_at, status)
- P2POffer(offer_id, request_id, lender_id, amount, interest_rate_apr, term_months, expires_at, status, accepted_at)
- Loan(loan_id, source_type, source_id, borrower_id, lender_id, product_id, principal_amount, currency_code, interest_rate_apr, term_months, start_date, maturity_date, repayment_schedule_json, status, created_at)
- LoanParticipant(loan_id, participant_type, participant_id, role, share_percent)
- RepaymentSchedule(schedule_id, loan_id, installment_no, due_date, due_principal, due_interest, fees_due, currency_code, status)
- Payment(payment_id, loan_id, schedule_id, payer_type, payer_id, amount, currency_code, paid_at, method, reference, status)
- DelinquencyEvent(event_id, loan_id, schedule_id, days_past_due, bucket, noted_at, status)
- Restructuring(restructure_id, loan_id, reason, new_term_months, new_rate_apr, effective_date, approved_by, approved_at)
- Dispute(dispute_id, loan_id, raised_by_type, raised_by_id, reason, status, opened_at, resolved_at, resolution_notes)
- RatingReview(review_id, rater_id, ratee_id, loan_id, rating, comment, created_at, updated_at)
- Notification(notification_id, recipient_type, recipient_id, channel, template_key, payload_json, sent_at, status)
- Document(document_id, owner_type, owner_id, category, file_url, checksum, uploaded_at, verified_at, status)
- AuditLog(audit_id, actor_type, actor_id, action, entity_type, entity_id, old_values_json, new_values_json, ip_address, user_agent, occurred_at)
### 4.2  API Design
- Style: REST (FastAPI)
- Base URL: /api/v1
- Auth: JWT Bearer via Authorization: Bearer <token>
- Content-Type: application/json
### 4.3 Application Logic
- borrowers need to pass credit checks --> data is taken from db and passed through alorithm to determine borrower risk rate
- borrower payment information is taken and stored in db --> automatic payments to creditor
- creditor dashboard which displays all different borrowers and information from their invesments
### 4.4 User Interface
- Tech: HTML/CSS/JS (lightweight, responsive)
- Theme: Clean tables + simple forms
## 5. Technlology Stack
**Frontend** - HMTL, CSS, JS
**Backend** - Python, Fast API
**Database** - SQL
**Hosting** - Railway
## 6. Security & Compliance
- JWT-based authentication, role-based access control  
- password hashing, TLS for all connections  
- input validation, prepared SQL statements  
- audit logging for all critical actions  
- basic compliance with KYC/AML flows  
## 7. Performance Considerations
- expected low-to-moderate load
- SQL indexes on frequent query fields  
- horizontal scaling possible on Railway if traffic grows  
- caching for common lookups
## 8. Risks & Mitigations
- **Fraud/abuse** --> KYC checks, role approvals  
- **Data breach** --> encryption, least privilege access  
- **Duplicate/failed payments** --> idempotency keys, transaction checks  
- **Performance issues** --> indexing, load testing, simple caching  
## 9. Testing Strategy
- unit tests for business logic  
- integration tests for API ↔ DB  
- end-to-end tests for loan lifecycle flows  
- basic security testing for inputs/authentication  
## 10. Deployment & Monitoring
- CI/CD with GitHub Actions --> Railway deploys  
- structured logging and error tracking  
- basic metrics (API latency, DB health)  
- alerts for failed deploys or high error rates  
