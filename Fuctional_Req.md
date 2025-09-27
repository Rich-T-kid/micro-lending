# Functional Requirements Document (FRD)
## 1. Document Control
- **Version:** 1.0  
- **Author:** Richard Baah, Jose Lamela, Saksham Mehta
- **Date:** 2025-09-14
- **Reviewers:** Development Team, Product Owner, Stakeholders  
## 2. Purpose
The purpose of this project is to build a **microlending platform** that enables users to request and fund small loans.  
The system will support both **borrowers** (individuals requesting loans) and **lenders** (individuals or institutions providing funds).  
It includes features for loan application, risk assessment, repayment tracking, compliance, and administrative oversight.  
## 3. Scope
- **In-Scope:**  
  - Borrower loan applications with flexible terms  
  - Lender portfolio management  
  - Loan approvals (manual and automated)  
  - Repayment schedules and delinquency reporting  
  - Identity verification and fraud detection  
  - Admin dashboards for user/loan management  
- **Out-of-Scope:**  
  - Cryptocurrency lending  
  - Large-scale institutional loans beyond $5,000  
  - Legal debt collection enforcement
## 4. Stakeholders
- **Borrowers** – individuals seeking loans  
- **Lenders** – peers and institutions providing funds  
- **Platform Administrators** – manage users and system operations  
- **Regulators/Compliance Officers** – oversee compliance reporting  
## 5. Functional Requirements
- **FR-1: Borrower Loan Application**  
  - Users can apply for loans with minimal documentation.  
  - **Acceptance Criteria:** Loan application saved with borrower details, requested amount, and repayment schedule.  
- **FR-2: Credit Assessment**  
  - System evaluates borrowers using traditional and alternative data (transaction history, mobile usage, social factors).  
  - **Acceptance Criteria:** Risk score generated and stored.  
- **FR-3: Lender Portfolio Management**  
  - Lenders can view, track, and diversify investments across multiple loans.  
  - **Acceptance Criteria:** Portfolio dashboard shows active, pending, and completed loans.  
- **FR-4: Repayment & Delinquency Tracking**  
  - Borrowers make repayments through integrated payment methods.  
  - System monitors overdue accounts and flags delinquencies.  
- **FR-5: Communication Tools**  
  - Borrowers and lenders can exchange messages about loan agreements.  
  - **Acceptance Criteria:** Secure chat thread stored with timestamps.  
- **FR-6: Admin User Management**  
  - Admins can create, suspend, and update borrower/lender accounts.  
  - **Acceptance Criteria:** Admin actions logged in audit trail.  
- **FR-7: Compliance & Risk Management**  
  - System generates compliance reports and alerts for suspicious activity.  
  - **Acceptance Criteria:** Regulatory report exportable as PDF/CSV.  
## 6. Non-Functional Requirements
- **Performance:** Loan application submission < 3s under typical load  
- **Security:** JWT-based authentication, password hashing, TLS, audit logging  
- **Scalability:** Railway hosting with horizontal scaling  
- **Usability:** Mobile-friendly responsive UI  
## 7. Assumptions & Dependencies
- Payment gateway integration (e.g., Stripe, PayPal, or mobile money)  
- Cloud-hosted SQL database  
- Document verification APIs for KYC  
## 8. Success Metrics
- 90% of loan applications processed without admin intervention  
- 95% repayment success rate with automated reminders  
- 99.5% system uptime  
- High user adoption and satisfaction rates  
