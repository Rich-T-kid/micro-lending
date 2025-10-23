from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Date, Text, Enum, ForeignKey
from sqlalchemy.types import DECIMAL, BIGINT, SMALLINT, CHAR, JSON, VARBINARY, TIMESTAMP
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, date
from decimal import Decimal as PyDecimal
from typing import Optional, Union

# Create declarative base
Base = declarative_base()

class Database:
    def __init__(self):
        # MySQL connection details
        # TODO: read from .env later
        MYSQL_HOST = "micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com"
        MYSQL_PORT = "3306"
        MYSQL_DATABASE = "microlending"
        MYSQL_USER = "admin"
        MYSQL_PASSWORD = "micropass"
        
        # Create engine
        DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._session = None
    
    def get_session(self):
        """Get database session, create if it doesn't exist"""
        if self._session is None:
            self._session = self.SessionLocal()
        return self._session


# Database Models
class UserAccount(Base):
    __tablename__ = "user_account"
    
    user_id = Column(BIGINT, primary_key=True, autoincrement=True)
    name_first = Column(String(80), nullable=False)
    name_last = Column(String(80), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(32), unique=True)
    date_of_birth = Column(Date)
    status = Column(Enum('active', 'suspended', 'closed'), default='active')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Role(Base):
    __tablename__ = "role"
    
    role_id = Column(TINYINT, primary_key=True)
    role_name = Column(Enum('BORROWER', 'LENDER', 'ADMIN'), unique=True)

class UserRole(Base):
    __tablename__ = "user_role"
    
    user_id = Column(BIGINT, ForeignKey('user_account.user_id'), primary_key=True)
    role_id = Column(TINYINT, ForeignKey('role.role_id'), primary_key=True)
    assigned_at = Column(TIMESTAMP, default=datetime.utcnow)

class IdentityKyc(Base):
    __tablename__ = "identity_kyc"
    
    kyc_id = Column(BIGINT, primary_key=True, autoincrement=True)
    user_id = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False, unique=True)
    government_id_type = Column(String(32))
    government_id_hash = Column(VARBINARY(64))
    address_line1 = Column(String(120))
    address_line2 = Column(String(120))
    city = Column(String(80))
    state = Column(String(80))
    postal_code = Column(String(20))
    country = Column(String(2))
    status = Column(Enum('pending', 'verified', 'failed'), default='pending')
    verified_at = Column(TIMESTAMP)

class Institution(Base):
    __tablename__ = "institution"
    
    institution_id = Column(BIGINT, primary_key=True, autoincrement=True)
    legal_name = Column(String(255), nullable=False, unique=True)
    type = Column(Enum('BANK', 'CREDIT_UNION', 'NGO', 'OTHER'), nullable=False)
    contact_email = Column(String(255))
    contact_phone = Column(String(32))
    status = Column(Enum('active', 'suspended', 'closed'), default='active')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Currency(Base):
    __tablename__ = "currency"
    
    currency_code = Column(CHAR(3), primary_key=True)
    name = Column(String(64))
    decimals = Column(TINYINT, nullable=False, default=2)

class WalletAccount(Base):
    __tablename__ = "wallet_account"
    
    account_id = Column(BIGINT, primary_key=True, autoincrement=True)
    owner_type = Column(Enum('USER', 'INSTITUTION'), nullable=False)
    owner_id = Column(BIGINT, nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    available_balance = Column(DECIMAL(18, 4), nullable=False, default=0)
    hold_balance = Column(DECIMAL(18, 4), nullable=False, default=0)
    status = Column(Enum('active', 'frozen', 'closed'), default='active')
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class LoanApplication(Base):
    __tablename__ = "loan_application"
    
    app_id = Column(BIGINT, primary_key=True, autoincrement=True)
    applicant_id = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False)
    channel = Column(Enum('P2P', 'INSTITUTION'), nullable=False)
    target_institution_id = Column(BIGINT, ForeignKey('institution.institution_id'))
    requested_amount = Column(DECIMAL(18, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    purpose = Column(String(255))
    term_months = Column(SMALLINT, nullable=False)
    collateral_flag = Column(Boolean, default=False)
    notes = Column(Text)
    status = Column(Enum('DRAFT', 'SUBMITTED', 'ASSESSING', 'OPEN_FOR_OFFERS', 'APPROVED', 'REJECTED', 'WITHDRAWN'), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class RiskAssessment(Base):
    __tablename__ = "risk_assessment"
    
    risk_id = Column(BIGINT, primary_key=True, autoincrement=True)
    app_id = Column(BIGINT, ForeignKey('loan_application.app_id'), nullable=False, unique=True)
    model_version = Column(String(32), nullable=False)
    score_numeric = Column(Integer, nullable=False)
    risk_band = Column(Enum('A', 'B', 'C', 'D', 'E'), nullable=False)
    dti_ratio = Column(DECIMAL(6, 3))
    income_verified = Column(Boolean, default=False)
    recommendation = Column(Enum('APPROVE', 'REVIEW', 'DECLINE'), nullable=False)
    assessed_at = Column(TIMESTAMP, default=datetime.utcnow)

class LoanOffer(Base):
    __tablename__ = "loan_offer"
    
    offer_id = Column(BIGINT, primary_key=True, autoincrement=True)
    app_id = Column(BIGINT, ForeignKey('loan_application.app_id'), nullable=False)
    lender_type = Column(Enum('USER', 'INSTITUTION'), nullable=False)
    lender_id = Column(BIGINT, nullable=False)
    principal_amount = Column(DECIMAL(18, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    interest_rate_apr = Column(DECIMAL(6, 3), nullable=False)
    repayment_type = Column(Enum('AMORTIZING', 'INTEREST_ONLY', 'BULLET'), nullable=False)
    term_months = Column(SMALLINT, nullable=False)
    grace_period_days = Column(SMALLINT, default=0)
    fees_flat = Column(DECIMAL(18, 2), default=0)
    fees_percent = Column(DECIMAL(5, 3), default=0)
    conditions_text = Column(Text)
    status = Column(Enum('PENDING', 'ACCEPTED', 'WITHDRAWN', 'EXPIRED', 'REJECTED'), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Loan(Base):
    __tablename__ = "loan"
    
    loan_id = Column(BIGINT, primary_key=True, autoincrement=True)
    app_id = Column(BIGINT, ForeignKey('loan_application.app_id'), nullable=False, unique=True)
    offer_id = Column(BIGINT, ForeignKey('loan_offer.offer_id'), nullable=False, unique=True)
    borrower_id = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False)
    lender_type = Column(Enum('USER', 'INSTITUTION'), nullable=False)
    lender_id = Column(BIGINT, nullable=False)
    principal_amount = Column(DECIMAL(18, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    interest_rate_apr = Column(DECIMAL(6, 3), nullable=False)
    origination_fee = Column(DECIMAL(18, 2), default=0)
    start_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    status = Column(Enum('ACTIVE', 'CLOSED', 'DEFAULTED', 'CHARGED_OFF'), nullable=False)

class RepaymentSchedule(Base):
    __tablename__ = "repayment_schedule"
    
    schedule_id = Column(BIGINT, primary_key=True, autoincrement=True)
    loan_id = Column(BIGINT, ForeignKey('loan.loan_id'), nullable=False)
    installment_no = Column(Integer, nullable=False)
    due_date = Column(Date, nullable=False)
    due_principal = Column(DECIMAL(18, 2), nullable=False, default=0)
    due_interest = Column(DECIMAL(18, 2), nullable=False, default=0)
    due_fees = Column(DECIMAL(18, 2), nullable=False, default=0)
    status = Column(Enum('PENDING', 'PARTIAL', 'PAID', 'LATE', 'WAIVED'), default='PENDING')
    paid_at = Column(TIMESTAMP)

class Disbursement(Base):
    __tablename__ = "disbursement"
    
    disb_id = Column(BIGINT, primary_key=True, autoincrement=True)
    loan_id = Column(BIGINT, ForeignKey('loan.loan_id'), nullable=False)
    from_account_id = Column(BIGINT, ForeignKey('wallet_account.account_id'), nullable=False)
    to_account_id = Column(BIGINT, ForeignKey('wallet_account.account_id'), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    status = Column(Enum('PENDING', 'POSTED', 'FAILED'), default='PENDING')

class Repayment(Base):
    __tablename__ = "repayment"
    
    pay_id = Column(BIGINT, primary_key=True, autoincrement=True)
    loan_id = Column(BIGINT, ForeignKey('loan.loan_id'), nullable=False)
    from_account_id = Column(BIGINT, ForeignKey('wallet_account.account_id'), nullable=False)
    to_account_id = Column(BIGINT, ForeignKey('wallet_account.account_id'), nullable=False)
    amount = Column(DECIMAL(18, 2), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    status = Column(Enum('PENDING', 'POSTED', 'FAILED'), default='PENDING')

class RepaymentAllocation(Base):
    __tablename__ = "repayment_allocation"
    
    allocation_id = Column(BIGINT, primary_key=True, autoincrement=True)
    pay_id = Column(BIGINT, ForeignKey('repayment.pay_id'), nullable=False)
    schedule_id = Column(BIGINT, ForeignKey('repayment_schedule.schedule_id'), nullable=False)
    to_principal = Column(DECIMAL(18, 2), nullable=False, default=0)
    to_interest = Column(DECIMAL(18, 2), nullable=False, default=0)
    to_fees = Column(DECIMAL(18, 2), nullable=False, default=0)

class TransactionLedger(Base):
    __tablename__ = "transaction_ledger"
    
    tx_id = Column(BIGINT, primary_key=True, autoincrement=True)
    related_type = Column(Enum('DISBURSEMENT', 'REPAYMENT', 'FEE', 'ADJUSTMENT', 'REVERSAL'), nullable=False)
    related_id = Column(BIGINT)
    account_id = Column(BIGINT, ForeignKey('wallet_account.account_id'), nullable=False)
    direction = Column(Enum('DEBIT', 'CREDIT'), nullable=False)
    amount = Column(DECIMAL(18, 4), nullable=False)
    currency_code = Column(CHAR(3), ForeignKey('currency.currency_code'), nullable=False)
    memo = Column(String(255))
    posted_by = Column(BIGINT, ForeignKey('user_account.user_id'))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class DelinquencyReport(Base):
    __tablename__ = "delinquency_report"
    
    dr_id = Column(BIGINT, primary_key=True, autoincrement=True)
    loan_id = Column(BIGINT, ForeignKey('loan.loan_id'), nullable=False)
    days_past_due = Column(Integer, nullable=False)
    snapshot_date = Column(Date, nullable=False)
    status = Column(Enum('CURRENT', 'DPD_30', 'DPD_60', 'DPD_90', 'DEFAULT'), nullable=False)

class MessageThread(Base):
    __tablename__ = "message_thread"
    
    thread_id = Column(BIGINT, primary_key=True, autoincrement=True)
    app_id = Column(BIGINT, ForeignKey('loan_application.app_id'), nullable=False)
    created_by = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "message"
    
    message_id = Column(BIGINT, primary_key=True, autoincrement=True)
    thread_id = Column(BIGINT, ForeignKey('message_thread.thread_id'), nullable=False)
    sender_type = Column(Enum('USER', 'INSTITUTION', 'ADMIN'), nullable=False)
    sender_id = Column(BIGINT, nullable=False)
    body_text = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class RatingReview(Base):
    __tablename__ = "rating_review"
    
    review_id = Column(BIGINT, primary_key=True, autoincrement=True)
    reviewer_id = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False)
    rating = Column(TINYINT, nullable=False)
    comment = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    audit_id = Column(BIGINT, primary_key=True, autoincrement=True)
    actor_id = Column(BIGINT, ForeignKey('user_account.user_id'))
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(BIGINT, nullable=False)
    old_values_json = Column(JSON)
    new_values_json = Column(JSON)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)



# Server models
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

class LoginRequest(BaseModel):
    email: str = Field(..., example="user@example.com", description="User email address")
    password: str = Field(..., example="mypassword123", description="User password")

    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "mypassword123"
            }
        }

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", description="JWT refresh token")

    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTY5ODc2NTQzMn0.ABC123"
            }
        }

class TokenResponse(BaseModel):
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", description="JWT access token")
    token_type: str = Field(..., example="bearer", description="Token type")
    refresh_token: Optional[str] = Field(None, example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", description="JWT refresh token (only on login)")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJlbWFpbCI6InVzZXJAZXhhbXBsZS5jb20iLCJleHAiOjE2OTg3NjE4MzJ9.ABC123",
                "token_type": "bearer",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTY5ODc2NTQzMn0.DEF456"
            }
        }

class UserCreateRequest(BaseModel):
    first_name: str = Field(..., example="Richard", description="User's first name")
    last_name: str = Field(..., example="Baah", description="User's last name")
    email: str = Field(..., example="user@example.com", description="User's email address")
    phone: Optional[str] = Field(None, example="424-233-1356", description="User's phone number")
    birthdate: Optional[str] = Field(None, example="2000-01-15", description="User's birth date in YYYY-MM-DD format")
    password: str = Field(..., example="securepassword123", description="User's password")
    preferred_language: Optional[str] = Field("en", example="en", description="User's preferred language code")
    marketing_consent: Optional[bool] = Field(False, example=False, description="Whether user consents to marketing emails")

    class Config:
        schema_extra = {
            "example": {
                "first_name": "Richard",
                "last_name": "Baah",
                "email": "user@example.com",
                "phone": "424-233-1356",
                "birthdate": "2000-01-15",
                "password": "securepassword123",
                "preferred_language": "en",
                "marketing_consent": False
            }
        }

class UserUpdateRequest(BaseModel):
    first_name: Optional[str] = Field(None, example="Richard", description="User's first name")
    last_name: Optional[str] = Field(None, example="Baah", description="User's last name")
    email: Optional[str] = Field(None, example="newemail@example.com", description="User's email address")
    phone: Optional[str] = Field(None, example="424-233-1356", description="User's phone number")
    birthdate: Optional[str] = Field(None, example="2000-01-15", description="User's birth date in YYYY-MM-DD format")
    status: Optional[str] = Field(None, example="active", description="User status: active, suspended, closed")
    preferred_language: Optional[str] = Field(None, example="en", description="User's preferred language code")
    marketing_consent: Optional[bool] = Field(None, example=True, description="Whether user consents to marketing emails")

    class Config:
        schema_extra = {
            "example": {
                "first_name": "Richard",
                "last_name": "Baah Updated",
                "email": "newemail@example.com",
                "phone": "555-123-4567",
                "status": "active"
            }
        }

class UserResponse(BaseModel):
    user_id: int = Field(..., example=1, description="User's unique identifier")
    email: str = Field(..., example="user@example.com", description="User's email address")
    first_name: str = Field(..., example="Richard", description="User's first name")
    last_name: str = Field(..., example="Baah", description="User's last name")
    phone: Optional[str] = Field(None, example="424-233-1356", description="User's phone number")
    birthdate: Optional[str] = Field(None, example="2000-01-15", description="User's birth date")
    status: str = Field(..., example="active", description="User status")
    created_at: str = Field(..., example="2023-10-19T10:30:00", description="Account creation timestamp")
    preferred_language: Optional[str] = Field(None, example="en", description="User's preferred language code")
    marketing_consent: Optional[bool] = Field(None, example=False, description="Whether user consents to marketing emails")

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "user_id": 1,
                "email": "user@example.com",
                "first_name": "Richard",
                "last_name": "Baah",
                "phone": "424-233-1356",
                "birthdate": "2000-01-15",
                "status": "active",
                "created_at": "2023-10-19T10:30:00",
                "preferred_language": "en",
                "marketing_consent": False
            }
        }

# KYC/Identity Verification Models
class KYCSubmissionRequest(BaseModel):
    government_id_type: str = Field(..., example="drivers_license", description="Type of government ID")
    government_id_number: str = Field(..., example="DL123456789", description="Government ID number (will be hashed)")
    address_line_1: str = Field(..., example="123 Main Street", description="Primary address line")
    address_line_2: Optional[str] = Field(None, example="Apt 4B", description="Secondary address line")
    city: str = Field(..., example="Los Angeles", description="City")
    state: Optional[str] = Field(None, example="CA", description="State/Province")
    postal_code: Optional[str] = Field(None, example="90210", description="Postal/ZIP code")
    country: str = Field(..., example="US", description="Country code")

    class Config:
        schema_extra = {
            "example": {
                "government_id_type": "drivers_license",
                "government_id_number": "DL123456789",
                "address_line_1": "123 Main Street",
                "address_line_2": "Apt 4B",
                "city": "Los Angeles",
                "state": "CA",
                "postal_code": "90210",
                "country": "US"
            }
        }

class KYCResponse(BaseModel):
    kyc_id: int = Field(..., example=1, description="KYC record unique identifier")
    user_id: int = Field(..., example=1, description="User's unique identifier")
    government_id_type: str = Field(..., example="drivers_license", description="Type of government ID")
    address_line_1: str = Field(..., example="123 Main Street", description="Primary address line")
    address_line_2: Optional[str] = Field(None, example="Apt 4B", description="Secondary address line")
    city: str = Field(..., example="Los Angeles", description="City")
    state: Optional[str] = Field(None, example="CA", description="State/Province")
    postal_code: Optional[str] = Field(None, example="90210", description="Postal/ZIP code")
    country: str = Field(..., example="US", description="Country code")
    status: str = Field(..., example="pending", description="Verification status")
    verified_at: Optional[str] = Field(None, example="2023-10-20T15:30:00", description="Verification timestamp")

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "kyc_id": 1,
                "user_id": 1,
                "government_id_type": "drivers_license",
                "address_line_1": "123 Main Street",
                "address_line_2": "Apt 4B",
                "city": "Los Angeles",
                "state": "CA",
                "postal_code": "90210",
                "country": "US",
                "status": "pending",
                "verified_at": None
            }
        }

# Wallet Management Models
class CreateWalletRequest(BaseModel):
    currency_code: str = Field(..., example="USD", description="Currency code for the wallet account")

    class Config:
        schema_extra = {
            "example": {
                "currency_code": "USD"
            }
        }

class WalletAccountResponse(BaseModel):
    account_id: int = Field(..., example=1, description="Wallet account unique identifier")
    owner_type: str = Field(..., example="USER", description="Owner type")
    owner_id: int = Field(..., example=1, description="Owner unique identifier")
    currency_code: str = Field(..., example="USD", description="Currency code")
    available_balance: float = Field(..., example=1000.00, description="Available balance")
    hold_balance: float = Field(..., example=50.00, description="Amount temporarily held")
    total_balance: float = Field(..., example=1050.00, description="Total balance (available + hold)")
    status: str = Field(..., example="active", description="Account status")
    created_at: str = Field(..., example="2023-10-19T10:30:00", description="Account creation timestamp")

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "account_id": 1,
                "owner_type": "USER",
                "owner_id": 1,
                "currency_code": "USD",
                "available_balance": 1000.00,
                "hold_balance": 50.00,
                "total_balance": 1050.00,
                "status": "active",
                "created_at": "2023-10-19T10:30:00"
            }
        }

class TransactionResponse(BaseModel):
    tx_id: int = Field(..., example=1, description="Transaction unique identifier")
    related_type: str = Field(..., example="DEPOSIT", description="Type of related transaction")
    related_id: Optional[int] = Field(None, example=123, description="ID of related entity")
    account_id: int = Field(..., example=1, description="Wallet account ID")
    direction: str = Field(..., example="CREDIT", description="Transaction direction")
    amount: float = Field(..., example=100.00, description="Transaction amount")
    currency_code: str = Field(..., example="USD", description="Currency code")
    memo: Optional[str] = Field(None, example="Initial deposit", description="Transaction memo")
    posted_by: Optional[int] = Field(None, example=1, description="User who posted the transaction")
    created_at: str = Field(..., example="2023-10-19T10:30:00", description="Transaction timestamp")

    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "tx_id": 1,
                "related_type": "DEPOSIT",
                "related_id": None,
                "account_id": 1,
                "direction": "CREDIT",
                "amount": 100.00,
                "currency_code": "USD",
                "memo": "Initial deposit",
                "posted_by": 1,
                "created_at": "2023-10-19T10:30:00"
            }
        }

class PaginationInfo(BaseModel):
    page: int = Field(..., example=1, description="Current page number")
    limit: int = Field(..., example=20, description="Items per page")
    total_pages: int = Field(..., example=5, description="Total number of pages")
    total_count: int = Field(..., example=95, description="Total number of items")
    has_next: bool = Field(..., example=True, description="Whether there's a next page")
    has_prev: bool = Field(..., example=False, description="Whether there's a previous page")

class TransactionHistoryResponse(BaseModel):
    data: List[TransactionResponse] = Field(..., description="List of transactions")
    pagination: PaginationInfo = Field(..., description="Pagination information")

    class Config:
        schema_extra = {
            "example": {
                "data": [
                    {
                        "tx_id": 1,
                        "related_type": "DEPOSIT",
                        "related_id": None,
                        "account_id": 1,
                        "direction": "CREDIT",
                        "amount": 100.00,
                        "currency_code": "USD",
                        "memo": "Initial deposit",
                        "posted_by": 1,
                        "created_at": "2023-10-19T10:30:00"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "limit": 20,
                    "total_pages": 5,
                    "total_count": 95,
                    "has_next": True,
                    "has_prev": False
                }
            }
        }

# Loan Application Models
class CreateLoanApplicationRequest(BaseModel):
    requested_amount: float = Field(..., gt=0, example=5000.00, description="Loan amount requested")
    currency_code: str = Field(..., max_length=3, example="USD", description="Currency code")
    purpose: str = Field(..., max_length=50, example="business_expansion", description="Purpose category")
    purpose_description: Optional[str] = Field(None, max_length=1000, example="Expanding business operations", description="Detailed purpose description")
    term_months: int = Field(..., gt=0, le=360, example=12, description="Loan term in months")
    collateral_flag: bool = Field(default=False, description="Whether collateral is offered")
    collateral_description: Optional[str] = Field(None, max_length=1000, description="Description of collateral offered")
    target_institution_id: Optional[str] = Field(None, description="Target lending institution ID")
    employment_status: Optional[str] = Field(None, example="employed", description="Employment status")
    monthly_income: Optional[float] = Field(None, gt=0, description="Monthly income")
    monthly_expenses: Optional[float] = Field(None, ge=0, description="Monthly expenses")
    existing_debt: Optional[float] = Field(None, ge=0, description="Existing debt amount")
    business_revenue: Optional[float] = Field(None, ge=0, description="Annual business revenue")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")

    class Config:
        schema_extra = {
            "example": {
                "requested_amount": 12000,
                "currency_code": "USD",
                "purpose": "business_expansion",
                "purpose_description": "Expanding EventPulse server infrastructure to handle increased user traffic",
                "term_months": 36,
                "collateral_flag": False,
                "collateral_description": "",
                "target_institution_id": "8ac7d912-64de-4f2c-91a1-00954a2378b4",
                "employment_status": "employed",
                "monthly_income": 6500,
                "monthly_expenses": 3200,
                "existing_debt": 2000,
                "business_revenue": 120000,
                "notes": "Applicant has stable full-time employment and prior successful project funding history."
            }
        }

class UpdateLoanApplicationRequest(BaseModel):
    requested_amount: Optional[float] = Field(None, gt=0, description="Updated loan amount")
    purpose: Optional[str] = Field(None, max_length=50, description="Updated purpose category")
    purpose_description: Optional[str] = Field(None, max_length=1000, description="Updated purpose description")
    term_months: Optional[int] = Field(None, gt=0, le=360, description="Updated term")
    collateral_flag: Optional[bool] = Field(None, description="Updated collateral flag")
    collateral_description: Optional[str] = Field(None, max_length=1000, description="Updated collateral description")
    employment_status: Optional[str] = Field(None, description="Updated employment status")
    monthly_income: Optional[float] = Field(None, gt=0, description="Updated monthly income")
    monthly_expenses: Optional[float] = Field(None, ge=0, description="Updated monthly expenses")
    existing_debt: Optional[float] = Field(None, ge=0, description="Updated existing debt")
    business_revenue: Optional[float] = Field(None, ge=0, description="Updated business revenue")
    notes: Optional[str] = Field(None, max_length=2000, description="Updated notes")

class LoanApplicationResponse(BaseModel):
    application_id: int = Field(..., example=1, description="Application ID")
    applicant_id: int = Field(..., example=123, description="Applicant user ID")
    amount_requested: float = Field(..., example=5000.00, description="Requested amount")
    purpose: str = Field(..., example="Business expansion", description="Loan purpose")
    term_months: int = Field(..., example=12, description="Term in months")
    status: str = Field(..., example="pending", description="Application status")
    currency_code: str = Field(..., example="USD", description="Currency")
    created_at: datetime = Field(..., description="Application submission date")
    updated_at: datetime = Field(..., description="Last update date")

    class Config:
        schema_extra = {
            "example": {
                "application_id": 1,
                "applicant_id": 123,
                "amount_requested": 5000.00,
                "purpose": "Small business expansion",
                "term_months": 12,
                "status": "pending",
                "currency_code": "USD",
                "created_at": "2023-10-19T10:30:00",
                "updated_at": "2023-10-19T10:30:00"
            }
        }

# Risk Assessment Models
class CreateRiskAssessmentRequest(BaseModel):
    model_version: str = Field("v2.1", example="v2.1", description="Risk model version")
    force_refresh: bool = Field(False, description="Force new assessment even if recent one exists")

class RiskAssessmentResponse(BaseModel):
    assessment_id: int = Field(..., example=1, description="Assessment ID")
    application_id: int = Field(..., example=1, description="Loan application ID")
    score: float = Field(..., example=750.5, description="Risk score")
    grade: str = Field(..., example="A", description="Risk grade")
    probability_of_default: float = Field(..., example=0.05, description="Default probability")
    model_version: str = Field(..., example="v2.1", description="Model version used")
    created_at: datetime = Field(..., description="Assessment date")

    class Config:
        schema_extra = {
            "example": {
                "assessment_id": 1,
                "application_id": 1,
                "score": 750.5,
                "grade": "A",
                "probability_of_default": 0.05,
                "model_version": "v2.1",
                "created_at": "2023-10-19T10:30:00"
            }
        }

# Loan Offer Models
class CreateLoanOfferRequest(BaseModel):
    principal_amount: float = Field(..., ge=25, example=4500.00, description="Principal loan amount")
    currency_code: str = Field(..., max_length=3, example="USD", description="Currency code")
    interest_apr: float = Field(..., ge=0, le=100, example=5.5, description="Annual percentage rate")
    repayment_type: str = Field(..., example="AMORTIZING", description="Repayment schedule type (AMORTIZING, INTEREST_ONLY, BULLET)")
    term_months: int = Field(..., gt=0, le=360, example=12, description="Loan term in months")
    conditions: Optional[str] = Field(None, max_length=1000, description="Special conditions")

    class Config:
        schema_extra = {
            "example": {
                "principal_amount": 4500.00,
                "currency_code": "USD",
                "interest_apr": 5.5,
                "repayment_type": "AMORTIZING",
                "term_months": 12,
                "conditions": "Standard terms apply"
            }
        }

class LoanOfferResponse(BaseModel):
    offer_id: int = Field(..., example=1, description="Offer ID")
    application_id: int = Field(..., example=1, description="Application ID")
    lender_id: int = Field(..., example=456, description="Lender ID")
    interest_rate: float = Field(..., example=5.5, description="Interest rate")
    amount_offered: float = Field(..., example=4500.00, description="Offered amount")
    term_months: int = Field(..., example=12, description="Term in months")
    status: str = Field(..., example="pending", description="Offer status")
    created_at: datetime = Field(..., description="Offer creation date")

    class Config:
        schema_extra = {
            "example": {
                "offer_id": 1,
                "application_id": 1,
                "lender_id": 456,
                "interest_rate": 5.5,
                "amount_offered": 4500.00,
                "term_months": 12,
                "status": "pending",
                "expires_at": "2023-11-19T10:30:00",
                "created_at": "2023-10-19T10:30:00"
            }
        }

# Loan Management Models
class LoanResponse(BaseModel):
    loan_id: int = Field(..., example=1, description="Loan ID")
    borrower_id: int = Field(..., example=123, description="Borrower ID")
    lender_id: int = Field(..., example=456, description="Lender ID")
    principal_amount: float = Field(..., example=5000.00, description="Principal amount")
    interest_rate: float = Field(..., example=5.5, description="Interest rate")
    term_months: int = Field(..., example=12, description="Loan term")
    status: str = Field(..., example="active", description="Loan status")
    balance_remaining: float = Field(..., example=3000.00, description="Remaining balance")
    next_payment_due: Optional[datetime] = Field(None, description="Next payment due date")
    created_at: datetime = Field(..., description="Loan creation date")

    class Config:
        schema_extra = {
            "example": {
                "loan_id": 1,
                "borrower_id": 123,
                "lender_id": 456,
                "principal_amount": 5000.00,
                "interest_rate": 5.5,
                "term_months": 12,
                "status": "active",
                "balance_remaining": 3000.00,
                "next_payment_due": "2023-11-19T00:00:00",
                "created_at": "2023-10-19T10:30:00"
            }
        }

class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0, example=500.00, description="Payment amount")
    origin_account_id: int = Field(..., example=1, description="Source wallet account ID")
    memo: Optional[str] = Field(None, max_length=255, description="Payment memo")

class RepaymentResponse(BaseModel):
    repayment_id: int = Field(..., example=1, description="Repayment ID")
    loan_id: int = Field(..., example=1, description="Loan ID")
    amount: float = Field(..., example=500.00, description="Payment amount")
    principal_portion: float = Field(..., example=450.00, description="Principal portion")
    interest_portion: float = Field(..., example=50.00, description="Interest portion")
    balance_after: float = Field(..., example=2500.00, description="Balance after payment")
    payment_date: datetime = Field(..., description="Payment date")
    status: str = Field(..., example="completed", description="Payment status")

    class Config:
        schema_extra = {
            "example": {
                "repayment_id": 1,
                "loan_id": 1,
                "amount": 500.00,
                "principal_portion": 450.00,
                "interest_portion": 50.00,
                "balance_after": 2500.00,
                "payment_date": "2023-10-19T10:30:00",
                "status": "completed"
            }
        }

# Portfolio Management Models
class PortfolioSummaryResponse(BaseModel):
    total_invested: float = Field(..., example=50000.00, description="Total amount invested")
    active_loans: int = Field(..., example=25, description="Number of active loans")
    total_earned: float = Field(..., example=2500.00, description="Total interest earned")
    default_rate: float = Field(..., example=0.02, description="Portfolio default rate")
    average_return: float = Field(..., example=6.5, description="Average return rate")
    pending_payments: float = Field(..., example=1200.00, description="Pending payments")

    class Config:
        schema_extra = {
            "example": {
                "total_invested": 50000.00,
                "active_loans": 25,
                "total_earned": 2500.00,
                "default_rate": 0.02,
                "average_return": 6.5,
                "pending_payments": 1200.00
            }
        }

# Auto-lending Configuration Models
class UpdateAutoLendingConfigRequest(BaseModel):
    enabled: bool = Field(..., example=True, description="Enable auto-lending")
    max_investment_per_loan: Optional[float] = Field(None, gt=0, example=1000.00, description="Max per loan")
    max_total_investment: Optional[float] = Field(None, gt=0, example=10000.00, description="Max total investment")
    min_credit_grade: Optional[str] = Field(None, example="B", description="Minimum credit grade")
    preferred_loan_term_min: Optional[int] = Field(None, gt=0, example=6, description="Min term months")
    preferred_loan_term_max: Optional[int] = Field(None, gt=0, example=36, description="Max term months")

class AutoLendingConfigResponse(BaseModel):
    config_id: int = Field(..., example=1, description="Config ID")
    user_id: int = Field(..., example=123, description="User ID")
    enabled: bool = Field(..., example=True, description="Auto-lending enabled")
    max_investment_per_loan: Optional[float] = Field(None, example=1000.00, description="Max per loan")
    max_total_investment: Optional[float] = Field(None, example=10000.00, description="Max total")
    min_credit_grade: Optional[str] = Field(None, example="B", description="Min credit grade")
    updated_at: datetime = Field(..., description="Last update")

    class Config:
        schema_extra = {
            "example": {
                "config_id": 1,
                "user_id": 123,
                "enabled": True,
                "max_investment_per_loan": 1000.00,
                "max_total_investment": 10000.00,
                "min_credit_grade": "B",
                "updated_at": "2023-10-19T10:30:00"
            }
        }

# Admin Models
class AdminDashboardResponse(BaseModel):
    total_users: int = Field(..., example=1250, description="Total registered users")
    active_loans: int = Field(..., example=324, description="Number of active loans")
    pending_applications: int = Field(..., example=45, description="Pending loan applications")
    total_loan_volume: float = Field(..., example=2500000.00, description="Total loan volume")
    revenue_this_month: float = Field(..., example=45000.00, description="Monthly revenue")
    default_rate: float = Field(..., example=0.02, description="Platform default rate")
    compliance_issues: int = Field(..., example=3, description="Open compliance issues")

    class Config:
        schema_extra = {
            "example": {
                "total_users": 1250,
                "active_loans": 324,
                "pending_applications": 45,
                "total_loan_volume": 2500000.00,
                "revenue_this_month": 45000.00,
                "default_rate": 0.02,
                "compliance_issues": 3
            }
        }

class AdminLoanApprovalRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500, description="Admin approval notes")
    conditions: Optional[str] = Field(None, max_length=500, description="Special conditions")

class AdminLoanRejectionRequest(BaseModel):
    reason: str = Field(..., max_length=500, description="Rejection reason")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")

class FraudAlertResponse(BaseModel):
    alert_id: int = Field(..., example=1, description="Alert ID")
    user_id: int = Field(..., example=123, description="User ID involved")
    alert_type: str = Field(..., example="suspicious_activity", description="Type of alert")
    severity: str = Field(..., example="high", description="Alert severity")
    status: str = Field(..., example="open", description="Alert status")
    description: str = Field(..., example="Multiple loan applications from same IP", description="Alert description")
    created_at: datetime = Field(..., description="Alert creation time")

    class Config:
        schema_extra = {
            "example": {
                "alert_id": 1,
                "user_id": 123,
                "alert_type": "suspicious_activity",
                "severity": "high",
                "status": "open",
                "description": "Multiple loan applications from same IP",
                "created_at": "2023-10-19T10:30:00"
            }
        }

class AuditLogResponse(BaseModel):
    log_id: int = Field(..., example=1, description="Log entry ID")
    actor_id: int = Field(..., example=123, description="User who performed action")
    action: str = Field(..., example="loan_approval", description="Action performed")
    entity_type: str = Field(..., example="loan_application", description="Entity type affected")
    entity_id: int = Field(..., example=456, description="Entity ID affected")
    details: Optional[str] = Field(None, description="Additional details")
    timestamp: datetime = Field(..., description="Action timestamp")

    class Config:
        schema_extra = {
            "example": {
                "log_id": 1,
                "actor_id": 123,
                "action": "loan_approval",
                "entity_type": "loan_application",
                "entity_id": 456,
                "details": "Loan approved with special conditions",
                "timestamp": "2023-10-19T10:30:00"
            }
        }

class PlatformMetricsResponse(BaseModel):
    reporting_period: str = Field(..., example="2023-10", description="Reporting period")
    total_loans_originated: int = Field(..., example=156, description="Loans originated")
    total_loan_volume: float = Field(..., example=780000.00, description="Total loan volume")
    average_loan_size: float = Field(..., example=5000.00, description="Average loan size")
    default_rate: float = Field(..., example=0.025, description="Default rate")
    revenue_generated: float = Field(..., example=23400.00, description="Revenue generated")
    active_users: int = Field(..., example=1250, description="Active users")
    new_registrations: int = Field(..., example=89, description="New user registrations")

    class Config:
        schema_extra = {
            "example": {
                "reporting_period": "2023-10",
                "total_loans_originated": 156,
                "total_loan_volume": 780000.00,
                "average_loan_size": 5000.00,
                "default_rate": 0.025,
                "revenue_generated": 23400.00,
                "active_users": 1250,
                "new_registrations": 89
            }
        }

class RevenueReportResponse(BaseModel):
    reporting_period: str = Field(..., example="2023-Q3", description="Reporting period")
    breakdown_by: str = Field(..., example="month", description="Breakdown type")
    total_revenue: float = Field(..., example=145000.00, description="Total revenue")
    fee_revenue: float = Field(..., example=87000.00, description="Fee revenue")
    interest_revenue: float = Field(..., example=58000.00, description="Interest revenue")
    breakdown_data: List[dict] = Field(..., description="Detailed breakdown")

    class Config:
        schema_extra = {
            "example": {
                "reporting_period": "2023-Q3",
                "breakdown_by": "month",
                "total_revenue": 145000.00,
                "fee_revenue": 87000.00,
                "interest_revenue": 58000.00,
                "breakdown_data": [
                    {"period": "2023-07", "revenue": 48000.00},
                    {"period": "2023-08", "revenue": 52000.00},
                    {"period": "2023-09", "revenue": 45000.00}
                ]
            }
        }

# Admin Risk Management Models
class DelinquencyReportResponse(BaseModel):
    loan_id: int = Field(..., example=1, description="Loan ID")
    borrower_id: int = Field(..., example=123, description="Borrower ID")
    borrower_name: str = Field(..., example="John Doe", description="Borrower name")
    loan_amount: float = Field(..., example=5000.00, description="Original loan amount")
    balance_remaining: float = Field(..., example=3000.00, description="Remaining balance")
    days_past_due: int = Field(..., example=15, description="Days past due")
    last_payment_date: Optional[datetime] = Field(None, description="Last payment date")
    next_payment_due: datetime = Field(..., description="Next payment due date")
    risk_level: str = Field(..., example="medium", description="Risk level")

    class Config:
        schema_extra = {
            "example": {
                "loan_id": 1,
                "borrower_id": 123,
                "borrower_name": "John Doe",
                "loan_amount": 5000.00,
                "balance_remaining": 3000.00,
                "days_past_due": 15,
                "last_payment_date": "2023-10-01T10:30:00",
                "next_payment_due": "2023-10-15T00:00:00",
                "risk_level": "medium"
            }
        }

# Admin Financial Operations Models
class AdminTransactionResponse(BaseModel):
    tx_id: int = Field(..., example=1, description="Transaction ID")
    related_type: str = Field(..., example="LOAN_PAYMENT", description="Transaction type")
    related_id: Optional[int] = Field(None, example=123, description="Related entity ID")
    account_id: int = Field(..., example=1, description="Account ID")
    user_id: int = Field(..., example=123, description="User ID")
    user_name: str = Field(..., example="John Doe", description="User name")
    direction: str = Field(..., example="CREDIT", description="Transaction direction")
    amount: float = Field(..., example=100.00, description="Transaction amount")
    currency_code: str = Field(..., example="USD", description="Currency code")
    memo: Optional[str] = Field(None, example="Loan payment", description="Transaction memo")
    posted_by: int = Field(..., example=1, description="User who posted transaction")
    created_at: datetime = Field(..., description="Transaction timestamp")
    status: str = Field(..., example="completed", description="Transaction status")

    class Config:
        schema_extra = {
            "example": {
                "tx_id": 1,
                "related_type": "LOAN_PAYMENT",
                "related_id": 123,
                "account_id": 1,
                "user_id": 123,
                "user_name": "John Doe",
                "direction": "CREDIT",
                "amount": 100.00,
                "currency_code": "USD",
                "memo": "Monthly loan payment",
                "posted_by": 1,
                "created_at": "2023-10-19T10:30:00",
                "status": "completed"
            }
        }

class CreateRatingResponse(BaseModel):
    """Simple response model for rating submission"""
    rating_id: int = Field(..., example=1, description="Unique identifier for this rating")
    reviewee_id: int = Field(..., example=456789, description="Auto-generated reviewee ID")
    rating: int = Field(..., example=5, description="Star rating value from 1-5")
    comment: Optional[str] = Field(None, example="Excellent service!", description="Review comment text")
    date_created: datetime = Field(..., example="2023-10-19T10:30:00Z", description="When the rating was created")
    successful: bool = Field(..., example=True, description="Whether the rating was successfully created")

    class Config:
        schema_extra = {
            "example": {
                "rating_id": 1,
                "reviewee_id": 456789,
                "rating": 5,
                "comment": "Excellent service!",
                "date_created": "2023-10-19T10:30:00Z",
                "successful": True
            }
        }

# Rating and Review Models
class CreateRatingRequest(BaseModel):
    """Request model for submitting a new rating"""
    rating: int = Field(..., ge=1, le=5, example=5, description="Star rating from 1-5 (5 being the best)")
    comment: Optional[str] = Field(None, max_length=1000, example="Excellent service! Fast processing and great communication throughout the entire process.", description="Optional review comment (maximum 1000 characters)")

    class Config:
        schema_extra = {
            "example": {
                "rating": 5,
                "comment": "Excellent service! Fast processing and great communication throughout the entire process. Highly recommend!"
            }
        }

class RatingResponse(BaseModel):
    """Response model for rating data"""
    rating_id: int = Field(..., example=1, description="Unique identifier for this rating")
    reviewer_id: int = Field(..., example=123, description="ID of the user who submitted this rating")
    rating: int = Field(..., example=5, description="Star rating value from 1-5")
    review_text: Optional[str] = Field(None, example="Excellent service! Fast processing and great communication.", description="Review comment text (if provided)")
    created_at: datetime = Field(..., example="2023-10-19T10:30:00Z", description="Timestamp when the rating was submitted")

    class Config:
        schema_extra = {
            "example": {
                "rating_id": 1,
                "reviewer_id": 123,
                "rating": 5,
                "review_text": "Excellent service! Fast processing and great communication throughout the entire process. Highly recommend!",
                "created_at": "2023-10-19T10:30:00Z"
            }
        }