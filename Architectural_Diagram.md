# Architectural Diagram

## 1. Overview
The system is a **microlending platform** that allows borrowers to apply for small loans and lenders (peers or institutions) to fund them.  
It provides loan tracking, repayments, portfolio management, and administrative oversight.
## 2. Context Diagram
![Context Diagram](./images/contextDiagram.png)

**Actors:**  
- **Borrower** – applies for loans and makes repayments  
- **Lender/Institution** – funds loans and tracks portfolio  
- **Admin** – manages users, loans, and compliance  
- **Payment Gateway** – processes deposits and repayments  
## 3. Component Diagram
![Component Diagram](./images/componentDiagram.png)

**Components:**  
- **Frontend** (HTML, CSS, JS)  
- **Backend API** (Python, FastAPI)  
- **Database** (SQL)  
- **Auth Service** (JWT-based authentication)  
- **Payment Integration** (gateway for disbursement and repayment)  
## 4. Deployment Diagram
![Deployment Diagram](./images/deploymentDiagram.png)

- **Railway Hosting**  
- FastAPI backend container → Railway app service  
- SQL database → Railway managed DB service  
- Static frontend → Railway deployment or CDN  
## 5. Data Flow Diagram
![Data Flow Diagram](./images/dataflowDiagram.png)

- Borrower submits loan application → Backend API → Database  
- Lender reviews/approves loan → Backend API → Database  
- Repayment → Payment Gateway → Backend API → Database  
- Admin views reports → Backend API → Database  
## 6. Security Considerations
- All communication secured with **HTTPS/TLS**  
- **JWT authentication** with role-based access control  
- **Password hashing** for user credentials  
- **Audit logs** for critical actions  
- **Minimal PII storage** (only what is needed for KYC/loan processing)  
