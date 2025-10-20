from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Date, Text, Enum, ForeignKey
from sqlalchemy.types import DECIMAL, BIGINT, SMALLINT, CHAR, JSON, VARBINARY, TIMESTAMP
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, date
from decimal import Decimal as PyDecimal
from typing import Optional

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
    reviewee_id = Column(BIGINT, ForeignKey('user_account.user_id'), nullable=False)
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
from typing import Optional

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