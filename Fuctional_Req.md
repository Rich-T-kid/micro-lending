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
## 4. User Roles
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
## 7. Use Cases
- **UC‑1 Borrower applies for loan**  
- **Trigger:** Borrower clicks “Apply” 
- **Inputs:** amount, currency, term, purpose, attachments 
- **Main Flow:** System validates inputs → creates Application with status **SUBMITTED** → enqueues risk assessment → shows confirmation
- **Outputs:** Application ID, status=SUBMITTED, estimated review time

- **UC‑2 Lender submits offer**  
- **Inputs:** application_id, amount, APR/fees, expiry
- **Flow:** Validate caps → create Offer with status **PENDING** → notify Borrower
- **Outputs:** Offer ID; visible in Borrower’s thread

- **UC‑3 Admin approves & disburses**  
- **Preconditions:** KYC=**VERIFIED**; total accepted offers ≤ requested amount.  
- **Flow:** Admin sets Application **APPROVED** → creates **Loan** and initial **Disbursement** → posts ledger entries.  
- **Outputs:** Loan ID; borrower sees funded balance and schedule.

- **UC‑4 Borrower makes installment repayment**  
- **Inputs:** loan_id, amount (from gateway)
- **Flow:** Create **Repayment** → allocate to interest/fees/principal → update schedule status → recalc next due
- **Outputs:** Receipt; updated outstanding principal and next due date

- **UC‑5 Delinquency report (Admin)**  
- **Inputs:** as‑of date, product
- **Flow:** System aggregates overdue installments into DPD buckets  
- **Outputs:** Table + CSV export
## 8. Business Rules
1. **KYC gate:** An application **cannot** be approved or disbursed unless the borrower’s KYC status is **VERIFIED**
2. **Funding cap:** The sum of **accepted** offers for an application must **not exceed** the requested amount
3. **Offer expiry:** An offer cannot be accepted after its expiry timestamp
4. **Schedule integrity:** Repayment allocations must satisfy: payment = principal_applied + interest_applied + fees_applied
5. **No duplicate reviews:** A reviewer can submit **at most one** review per reviewee
6. **Currency consistency:** A loan’s currency must match its disbursements and repayments  
7. **State transitions:** Only Admin can move Application to APPROVED/DENIED and Loan to CHARGED_OFF/CLOSED
8. **Auditability:** Every financial mutation (disbursement, repayment, reversal) must write a ledger entry with immutable ID and timestamp