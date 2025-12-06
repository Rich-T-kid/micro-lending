from typing import Union, List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uuid
import datetime
import jwt
import hashlib
import os
import sys
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import models
try:
    from cache import get_redis_client, CacheKeyBuilder, ANALYTICS_TTL, get_cache_metrics
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    def get_redis_client(): return None
    def get_cache_metrics(): return None

# source .venv/bin/activate

# Create FastAPI instance with metadata
app = FastAPI(
    title="Micro-Lending API",
    description="A simple micro-lending platform API",
    version="1.0.0"
)

# Add CORS middleware to allow frontend to communicate with API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/")
async def read_root():
    """
    Hello World endpoint
    """
    return {"Hello": "World", "message": "Welcome to Micro-Lending API!"}

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "service": "micro-lending-api"}


Secret_key = os.getenv("JWT_SECRET", "default_dev_key_replace_in_env")
security = HTTPBearer()
db = models.Database()

# =============================================================================
# HELPER FUNCTIONS FOR REFACTORED 3NF SCHEMA
# =============================================================================

def get_loan_principal_amount(session, loan_id: int) -> float:
    """Get principal amount from loan_offer via loan relationship"""
    loan = session.query(models.Loan).filter(models.Loan.loan_id == loan_id).first()
    if not loan:
        return 0
    offer = session.query(models.LoanOffer).filter(models.LoanOffer.offer_id == loan.offer_id).first()
    return float(offer.principal_amount) if offer else 0

def get_loan_terms(session, loan_id: int):
    """Get loan terms (principal_amount, interest_rate_apr) from loan_offer"""
    loan = session.query(models.Loan).filter(models.Loan.loan_id == loan_id).first()
    if not loan:
        return None
    offer = session.query(models.LoanOffer).filter(models.LoanOffer.offer_id == loan.offer_id).first()
    if offer:
        return {
            'principal_amount': float(offer.principal_amount),
            'interest_rate_apr': float(offer.interest_rate_apr),
            'term_months': offer.term_months,
            'repayment_type': offer.repayment_type
        }
    return None

def get_all_loans_with_terms(session):
    """Get all loans with their terms (handles JOIN internally)"""
    return session.query(
        models.Loan,
        models.LoanOffer.principal_amount,
        models.LoanOffer.interest_rate_apr
    ).join(models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id).all()

# =============================================================================
# ROLE-BASED ACCESS CONTROL HELPER
# =============================================================================

def get_user_roles(session, user_id: int) -> List[str]:
    """Get all roles for a user from user_role junction table"""
    user_roles = session.query(models.UserRole).filter(
        models.UserRole.user_id == user_id
    ).all()
    roles = []
    for user_role in user_roles:
        role = session.query(models.Role).filter(
            models.Role.role_id == user_role.role_id
        ).first()
        if role:
            roles.append(role.role_name)
    return roles

def check_admin_role(session, user_id: int) -> bool:
    """Check if user has ADMIN role"""
    roles = get_user_roles(session, user_id)
    return 'ADMIN' in roles

def check_lender_role(session, user_id: int) -> bool:
    """Check if user has LENDER role"""
    roles = get_user_roles(session, user_id)
    return 'LENDER' in roles

def check_borrower_role(session, user_id: int) -> bool:
    """Check if user has BORROWER role"""
    roles = get_user_roles(session, user_id)
    return 'BORROWER' in roles

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, Secret_key, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== AUTH ROUTES ====================

@app.post("/auth/login", response_model=models.TokenResponse)
async def login(request: models.LoginRequest):
    """User login endpoint"""
    session = db.get_session()
    try:
        # Find user by email
        user = session.query(models.UserAccount).filter(
            models.UserAccount.email == request.email
        ).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # In a real app, you'd verify the hashed password
        # For now, we'll just check if user exists
        
        payload = {
            "user_id": user.user_id,
            "email": user.email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        
        refresh_payload = {
            "user_id": user.user_id,
            "type": "refresh",
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }
        
        access_token = jwt.encode(payload, Secret_key, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, Secret_key, algorithm="HS256")
        
        return models.TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 401) without converting to 500
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/auth/refresh", response_model=models.TokenResponse)
async def refresh_token(request: models.RefreshTokenRequest):
    """Refresh access token"""
    try:
        payload = jwt.decode(request.refresh_token, Secret_key, algorithms=["HS256"])
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        user_id = payload.get("user_id")
        session = db.get_session()
        
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        new_payload = {
            "user_id": user.user_id,
            "email": user.email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        
        access_token = jwt.encode(new_payload, Secret_key, algorithm="HS256")
        
        return models.TokenResponse(
            access_token=access_token,
            token_type="bearer"
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except HTTPException:
        # Re-raise HTTP exceptions without converting to 500
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# ==================== USER MANAGEMENT ROUTES ====================

@app.post("/users", response_model=models.UserResponse, status_code=201)
async def create_user(user_data: models.UserCreateRequest):
    """Create a new user"""
    session = db.get_session()
    print(f"user data{user_data}")
    try:
        # Parse date if provided
        date_of_birth = None
        if user_data.birthdate:
            date_of_birth = datetime.datetime.strptime(user_data.birthdate, "%Y-%m-%d").date()
        
        # Create new user (map API fields to database fields)
        new_user = models.UserAccount(
            email=user_data.email,
            name_first=user_data.first_name,  # Map first_name to name_first
            name_last=user_data.last_name,    # Map last_name to name_last
            phone=user_data.phone,
            date_of_birth=date_of_birth,      # Map birthdate to date_of_birth
            status='active'
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        return models.UserResponse(
            user_id=new_user.user_id,
            email=new_user.email,
            first_name=new_user.name_first,   # Map name_first to first_name
            last_name=new_user.name_last,     # Map name_last to last_name
            phone=new_user.phone,
            birthdate=str(new_user.date_of_birth) if new_user.date_of_birth else None,
            status=new_user.status,
            created_at=str(new_user.created_at),
            preferred_language=user_data.preferred_language,
            marketing_consent=user_data.marketing_consent
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    except HTTPException:
        # Re-raise HTTP exceptions without converting to 500
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users", response_model=List[models.UserResponse])
async def list_users(skip: int = 0, limit: int = 100):
    """List all users with pagination"""
    session = db.get_session()
    try:
        users = session.query(models.UserAccount).offset(skip).limit(limit).all()
        
        return [
            models.UserResponse(
                user_id=user.user_id,
                email=user.email,
                first_name=user.name_first,   # Map database field to API field
                last_name=user.name_last,     # Map database field to API field
                phone=user.phone,
                birthdate=str(user.date_of_birth) if user.date_of_birth else None,
                status=user.status,
                created_at=str(user.created_at),
                preferred_language="en",  # Default value since not stored in DB yet
                marketing_consent=False   # Default value since not stored in DB yet
            ) for user in users
        ]
    except HTTPException:
        # Re-raise HTTP exceptions without converting to 500
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}", response_model=models.UserResponse)
async def get_user_profile(user_id: int):
    """Get user profile by ID"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return models.UserResponse(
            user_id=user.user_id,
            email=user.email,
            first_name=user.name_first,   # Map database field to API field
            last_name=user.name_last,     # Map database field to API field
            phone=user.phone,
            birthdate=str(user.date_of_birth) if user.date_of_birth else None,
            status=user.status,
            created_at=str(user.created_at),
            preferred_language="en",  # Default value since not stored in DB yet
            marketing_consent=False   # Default value since not stored in DB yet
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.put("/users/{user_id}", response_model=models.UserResponse)
async def update_user(user_id: int, user_data: models.UserUpdateRequest):
    """Update user profile"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update only provided fields (map API fields to database fields)
        update_data = user_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "first_name":
                setattr(user, "name_first", value)
            elif field == "last_name":
                setattr(user, "name_last", value)
            elif field == "birthdate" and value:
                setattr(user, "date_of_birth", datetime.datetime.strptime(value, "%Y-%m-%d").date())
            elif field in ["preferred_language", "marketing_consent"]:
                # Skip these fields as they're not in the database yet
                continue
            else:
                setattr(user, field, value)
        
        session.commit()
        session.refresh(user)
        
        return models.UserResponse(
            user_id=user.user_id,
            email=user.email,
            first_name=user.name_first,   # Map database field to API field
            last_name=user.name_last,     # Map database field to API field
            phone=user.phone,
            birthdate=str(user.date_of_birth) if user.date_of_birth else None,
            status=user.status,
            created_at=str(user.created_at),
            preferred_language="en",  # Default value since not stored in DB yet
            marketing_consent=False   # Default value since not stored in DB yet
        )
    except HTTPException:
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """Delete user (soft delete by setting status to 'closed')"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Soft delete by changing status
        user.status = 'closed'
        session.commit()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# ==================== IDENTITY VERIFICATION ROUTES ====================

@app.post("/users/{user_id}/kyc", response_model=models.KYCResponse, status_code=201)
async def submit_kyc_information(user_id: int, kyc_data: models.KYCSubmissionRequest):
    """Submit KYC information for identity verification"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if KYC already exists for this user
        existing_kyc = session.query(models.IdentityKyc).filter(
            models.IdentityKyc.user_id == user_id
        ).first()
        
        if existing_kyc:
            raise HTTPException(status_code=400, detail="KYC information already submitted for this user")
        
        # Hash the government ID number for security
        id_hash = hash_password(kyc_data.government_id_number)
        
        # Create new KYC record
        new_kyc = models.IdentityKyc(
            user_id=user_id,
            government_id_type=kyc_data.government_id_type,
            government_id_hash=id_hash.encode('utf-8'),  # Store as bytes
            address_line1=kyc_data.address_line_1,
            address_line2=kyc_data.address_line_2,
            city=kyc_data.city,
            state=kyc_data.state,
            postal_code=kyc_data.postal_code,
            country=kyc_data.country,
            status='pending'
        )
        
        session.add(new_kyc)
        session.commit()
        session.refresh(new_kyc)
        
        return models.KYCResponse(
            kyc_id=new_kyc.kyc_id,
            user_id=new_kyc.user_id,
            government_id_type=new_kyc.government_id_type,
            address_line_1=new_kyc.address_line1,
            address_line_2=new_kyc.address_line2,
            city=new_kyc.city,
            state=new_kyc.state,
            postal_code=new_kyc.postal_code,
            country=new_kyc.country,
            status=new_kyc.status,
            verified_at=str(new_kyc.verified_at) if new_kyc.verified_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}/kyc", response_model=models.KYCResponse)
async def get_kyc_status(user_id: int):
    """Get KYC verification status for a user"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get KYC record
        kyc_record = session.query(models.IdentityKyc).filter(
            models.IdentityKyc.user_id == user_id
        ).first()
        
        if not kyc_record:
            raise HTTPException(status_code=404, detail="No KYC information found for this user")
        
        return models.KYCResponse(
            kyc_id=kyc_record.kyc_id,
            user_id=kyc_record.user_id,
            government_id_type=kyc_record.government_id_type,
            address_line_1=kyc_record.address_line1,
            address_line_2=kyc_record.address_line2,
            city=kyc_record.city,
            state=kyc_record.state,
            postal_code=kyc_record.postal_code,
            country=kyc_record.country,
            status=kyc_record.status,
            verified_at=str(kyc_record.verified_at) if kyc_record.verified_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# ==================== WALLET MANAGEMENT ROUTES ====================

@app.get("/users/{user_id}/accounts", response_model=List[models.WalletAccountResponse])
async def get_user_wallet_accounts(user_id: int):
    """Get user wallet accounts"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get all wallet accounts for the user
        accounts = session.query(models.WalletAccount).filter(
            models.WalletAccount.owner_type == 'USER',
            models.WalletAccount.owner_id == user_id
        ).all()
        
        return [
            models.WalletAccountResponse(
                account_id=account.account_id,
                owner_type=account.owner_type,
                owner_id=account.owner_id,
                currency_code=account.currency_code,
                available_balance=float(account.available_balance),
                hold_balance=float(account.hold_balance),
                total_balance=float(account.available_balance + account.hold_balance),
                status=account.status,
                created_at=str(account.created_at)
            ) for account in accounts
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/users/{user_id}/accounts", response_model=models.WalletAccountResponse, status_code=201)
async def create_wallet_account(user_id: int, wallet_data: models.CreateWalletRequest):
    """Create new wallet account"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if currency exists
        currency = session.query(models.Currency).filter(
            models.Currency.currency_code == wallet_data.currency_code
        ).first()
        
        if not currency:
            raise HTTPException(status_code=400, detail=f"Currency {wallet_data.currency_code} not supported")
        
        # Check if user already has an account in this currency
        existing_account = session.query(models.WalletAccount).filter(
            models.WalletAccount.owner_type == 'USER',
            models.WalletAccount.owner_id == user_id,
            models.WalletAccount.currency_code == wallet_data.currency_code
        ).first()
        
        if existing_account:
            raise HTTPException(status_code=400, detail=f"User already has a {wallet_data.currency_code} account")
        
        # Create new wallet account
        new_account = models.WalletAccount(
            owner_type='USER',
            owner_id=user_id,
            currency_code=wallet_data.currency_code,
            available_balance=0.0,
            hold_balance=0.0,
            status='active'
        )
        
        session.add(new_account)
        session.commit()
        session.refresh(new_account)
        
        return models.WalletAccountResponse(
            account_id=new_account.account_id,
            owner_type=new_account.owner_type,
            owner_id=new_account.owner_id,
            currency_code=new_account.currency_code,
            available_balance=float(new_account.available_balance),
            hold_balance=float(new_account.hold_balance),
            total_balance=float(new_account.available_balance + new_account.hold_balance),
            status=new_account.status,
            created_at=str(new_account.created_at)
        )
    except HTTPException:
        raise
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Wallet account creation failed")
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/accounts/{account_id}/transactions", response_model=models.TransactionHistoryResponse)
async def get_account_transactions(
    account_id: int,
    page: int = 1,
    limit: int = 20,
    transaction_type: Optional[str] = None
):
    """Get account transaction history"""
    session = db.get_session()
    try:
        # Check if account exists
        account = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == account_id
        ).first()
        
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Build query for transactions
        query = session.query(models.TransactionLedger).filter(
            models.TransactionLedger.account_id == account_id
        )
        
        # Filter by transaction type if provided
        if transaction_type:
            query = query.filter(models.TransactionLedger.related_type == transaction_type.upper())
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        transactions = query.order_by(models.TransactionLedger.created_at.desc()).offset(offset).limit(limit).all()
        
        # Calculate pagination info
        total_pages = (total_count + limit - 1) // limit
        has_next = page < total_pages
        has_prev = page > 1
        
        # Format response
        transaction_data = [
            models.TransactionResponse(
                tx_id=tx.tx_id,
                related_type=tx.related_type,
                related_id=tx.related_id,
                account_id=tx.account_id,
                direction=tx.direction,
                amount=float(tx.amount),
                currency_code=tx.currency_code,
                memo=tx.memo,
                posted_by=tx.posted_by,
                created_at=str(tx.created_at)
            ) for tx in transactions
        ]
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return models.TransactionHistoryResponse(
            data=transaction_data,
            pagination=pagination_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# =============================================================================
# LOAN APPLICATION ENDPOINTS
# =============================================================================


@app.get("/users/{user_id}/loan-application")
async def get_user_loan_applications_simple(user_id: int):
    """Get all loan applications for a user"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User account does not exist")
        
        # Get all loan applications for the user
        applications = session.query(models.LoanApplication).filter(
            models.LoanApplication.applicant_id == user_id
        ).all()
        
        application_data = []
        for app in applications:
            application_data.append({
                "application_id": app.app_id,
                "applicant_id": app.applicant_id,
                "amount_requested": float(app.requested_amount),
                "purpose": app.purpose,
                "term_months": app.term_months,
                "status": app.status,
                "currency_code": app.currency_code,
                "created_at": app.created_at,
                "updated_at": app.created_at  # DB schema doesn't have updated_at, use created_at
            })
        
        return {"data": application_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/users/{user_id}/loan-application", response_model=models.LoanApplicationResponse)
async def create_loan_application(
    user_id: int,
    application_data: models.CreateLoanApplicationRequest
):
    """Submit a new loan application for a user"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create new loan application
        new_application = models.LoanApplication(
            applicant_id=user_id,
            requested_amount=application_data.requested_amount,  # Use correct field name from DB schema
            purpose=application_data.purpose,
            term_months=application_data.term_months,
            currency_code=application_data.currency_code,
            collateral_flag=application_data.collateral_flag,
            notes=application_data.notes,
            channel='P2P',  # Default channel
            status='SUBMITTED'  # Use correct enum value
        )
        
        session.add(new_application)
        session.commit()
        session.refresh(new_application)
        
        return models.LoanApplicationResponse(
            application_id=new_application.app_id,  # Use correct field name from DB
            applicant_id=new_application.applicant_id,
            amount_requested=new_application.requested_amount,  # Use correct field name from DB
            purpose=new_application.purpose,
            term_months=new_application.term_months,
            status=new_application.status,
            currency_code=new_application.currency_code,
            created_at=new_application.created_at,
            updated_at=new_application.created_at  # DB schema doesn't have updated_at, use created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()



@app.get("/users/{user_id}/loan-applications/{application_id}", response_model=models.LoanApplicationResponse)
async def get_loan_application(user_id: int, application_id: int):
    """Get specific loan application details"""
    session = db.get_session()
    try:
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == application_id,  # Use correct field name from DB schema
            models.LoanApplication.applicant_id == user_id
        ).first()
        print("application found -> f{application}")
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        return models.LoanApplicationResponse(
            application_id=application.app_id,  # Use correct field name from DB schema
            applicant_id=application.applicant_id,
            amount_requested=application.requested_amount,  # Use correct field name from DB schema
            purpose=application.purpose,
            term_months=application.term_months,
            status=application.status,
            currency_code=application.currency_code,
            created_at=application.created_at,
            updated_at=application.created_at  # DB schema doesn't have updated_at, use created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.put("/users/{user_id}/loan-applications/{application_id}", response_model=models.LoanApplicationResponse)
async def update_loan_application(
    user_id: int,
    application_id: int,
    update_data: models.UpdateLoanApplicationRequest
):
    """Update loan application (before approval)"""
    session = db.get_session()
    try:
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == application_id,  # Use correct field name from DB schema
            models.LoanApplication.applicant_id == user_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        if application.status != 'SUBMITTED':  # Use correct enum value
            raise HTTPException(status_code=400, detail="Can only update submitted applications")
        
        # Update fields
        if update_data.requested_amount is not None:
            application.requested_amount = update_data.requested_amount  # Use correct field name
        if update_data.purpose is not None:
            application.purpose = update_data.purpose
        if update_data.term_months is not None:
            application.term_months = update_data.term_months
        if update_data.collateral_flag is not None:
            application.collateral_flag = update_data.collateral_flag
        if update_data.notes is not None:
            application.notes = update_data.notes
        
        session.commit()
        session.refresh(application)
        
        return models.LoanApplicationResponse(
            application_id=application.app_id,  # Use correct field name from DB schema
            applicant_id=application.applicant_id,
            amount_requested=application.requested_amount,  # Use correct field name from DB schema
            purpose=application.purpose,
            term_months=application.term_months,
            status=application.status,
            currency_code=application.currency_code,
            created_at=application.created_at,
            updated_at=application.created_at  # DB schema doesn't have updated_at, use created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# =============================================================================
# RISK ASSESSMENT ENDPOINTS
# =============================================================================
# Note: Risk assessment runs on-demand; could be automated via cron job
@app.get("/users/{user_id}/loan-applications/{application_id}/risk-assessment", response_model=models.RiskAssessmentResponse)
async def get_risk_assessment(user_id: int, application_id: int):
    """Get risk assessment for loan application"""
    session = db.get_session()
    try:
        # Check if application exists and belongs to user
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == application_id,
            models.LoanApplication.applicant_id == user_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        assessment = session.query(models.RiskAssessment).filter(
            models.RiskAssessment.app_id == application_id
        ).first()
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        
        return models.RiskAssessmentResponse(
            assessment_id=assessment.risk_id,
            application_id=assessment.app_id,
            score=assessment.score_numeric,
            grade=assessment.risk_band,
            probability_of_default=0.05,  # Default value since this field doesn't exist in schema
            model_version=assessment.model_version,
            created_at=assessment.assessed_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# LOAN OFFER ENDPOINTS
# =============================================================================

@app.get("/users/{user_id}/loan-applications/{application_id}/offers", response_model=List[models.LoanOfferResponse])
async def get_loan_offers(user_id: int, application_id: int):
    """Get loan offers for application"""
    session = db.get_session()
    try:
        # Check if application exists and belongs to user
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == application_id,
            models.LoanApplication.applicant_id == user_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        offers = session.query(models.LoanOffer).filter(
            models.LoanOffer.app_id == application_id
        ).all()
        
        return [
            models.LoanOfferResponse(
                offer_id=offer.offer_id,
                application_id=offer.app_id,  # Use correct database field
                lender_id=offer.lender_id,
                interest_rate=offer.interest_rate_apr,  # Use correct database field
                amount_offered=offer.principal_amount,  # Use correct database field
                term_months=offer.term_months,
                status=offer.status,
                created_at=offer.created_at
            ) for offer in offers
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/users/{user_id}/loan-applications/{application_id}/offers", response_model=models.LoanOfferResponse)
async def create_loan_offer(
    user_id: int,
    application_id: int,
    offer_data: models.CreateLoanOfferRequest
):
    """Create loan offer (Lender/Admin)"""
    session = db.get_session()
    try:
        # Check if application exists
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == application_id,
            models.LoanApplication.applicant_id == user_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        # For now, use a default lender_id (in real app, this would come from auth)
        lender_id = 1  # This should be from JWT token in real implementation
        
        from datetime import datetime, timedelta
        
        new_offer = models.LoanOffer(
            app_id=application_id,
            lender_type='USER',  # Default to USER type
            lender_id=lender_id,
            principal_amount=offer_data.principal_amount,
            currency_code=offer_data.currency_code,  # Use from request instead of hardcoded
            interest_rate_apr=offer_data.interest_apr,  # Use correct field name
            repayment_type=offer_data.repayment_type,  # Use from request instead of hardcoded
            term_months=offer_data.term_months,
            conditions_text=offer_data.conditions,  # Use correct field name
            status='PENDING'
        )
        
        session.add(new_offer)
        session.commit()
        session.refresh(new_offer)
        
        return models.LoanOfferResponse(
            offer_id=new_offer.offer_id,
            application_id=new_offer.app_id,  # Use correct database field
            lender_id=new_offer.lender_id,
            interest_rate=new_offer.interest_rate_apr,  # Use correct database field
            amount_offered=new_offer.principal_amount,  # Use correct database field
            term_months=new_offer.term_months,
            status=new_offer.status,
            created_at=new_offer.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/loan-offers/{offer_id}/accept", response_model=models.LoanResponse)
async def accept_loan_offer(offer_id: int):
    """Accept loan offer (Borrower) - creates a loan from the accepted offer"""
    session = db.get_session()
    try:
        # Get the offer with application details
        offer = session.query(models.LoanOffer).filter(
            models.LoanOffer.offer_id == offer_id
        ).first()
        
        if not offer:
            raise HTTPException(status_code=404, detail="Loan offer not found")
        
        if offer.status != 'PENDING':
            raise HTTPException(status_code=400, detail=f"Offer is {offer.status}, cannot accept")
        
        # Get the application to find borrower
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == offer.app_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Check if loan already exists for this offer
        existing_loan = session.query(models.Loan).filter(
            models.Loan.offer_id == offer_id
        ).first()
        
        if existing_loan:
            raise HTTPException(status_code=400, detail="Loan already created for this offer")
        
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        # Create the loan from the offer
        start_date = date.today()
        maturity_date = start_date + relativedelta(months=offer.term_months)
        
        new_loan = models.Loan(
            app_id=offer.app_id,
            offer_id=offer.offer_id,
            borrower_id=application.applicant_id,
            lender_type=offer.lender_type,
            lender_id=offer.lender_id,
            currency_code=offer.currency_code,
            origination_fee=offer.fees_flat or 0,
            start_date=start_date,
            maturity_date=maturity_date,
            status='ACTIVE'
        )
        
        session.add(new_loan)
        
        # Update offer status to accepted
        offer.status = 'ACCEPTED'
        
        # Update application status
        application.status = 'approved'
        
        session.commit()
        session.refresh(new_loan)
        
        return models.LoanResponse(
            loan_id=new_loan.loan_id,
            borrower_id=new_loan.borrower_id,
            lender_id=new_loan.lender_id,
            principal_amount=float(offer.principal_amount),
            interest_rate=float(offer.interest_rate_apr),
            term_months=offer.term_months,
            status=new_loan.status.lower(),
            balance_remaining=float(offer.principal_amount),
            created_at=str(new_loan.start_date)
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# LOAN MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/users/{user_id}/loans", response_model=models.TransactionHistoryResponse)
async def get_user_loans(
    user_id: int,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """List loans for user (as borrower or lender)"""
    session = db.get_session()
    try:
        # Get loans where user is either borrower or lender
        query = session.query(models.Loan).filter(
            (models.Loan.borrower_id == user_id) | (models.Loan.lender_id == user_id)
        )
        
        if status:
            query = query.filter(models.Loan.status == status)
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        loans = query.offset((page - 1) * limit).limit(limit).all()
        
        loan_data = [
            models.LoanResponse(
                loan_id=loan.loan_id,
                borrower_id=loan.borrower_id,
                lender_id=loan.lender_id,
                principal_amount=loan.principal_amount,
                interest_rate=loan.interest_rate,
                term_months=loan.term_months,
                status=loan.status,
                balance_remaining=loan.balance_remaining,
                next_payment_due=loan.next_payment_due,
                created_at=loan.created_at
            ) for loan in loans
        ]
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return models.TransactionHistoryResponse(
            data=loan_data,
            pagination=pagination_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}/loans/{loan_id}", response_model=models.LoanResponse)
async def get_loan_details(user_id: int, loan_id: int):
    """Get loan details"""
    session = db.get_session()
    try:
        loan = session.query(models.Loan).filter(
            models.Loan.loan_id == loan_id,
            (models.Loan.borrower_id == user_id) | (models.Loan.lender_id == user_id)
        ).first()
        
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")
        
        # REFACTORED 3NF: Get loan terms from loan_offer
        loan_terms = get_loan_terms(session, loan_id)
        if not loan_terms:
            raise HTTPException(status_code=500, detail="Loan offer not found")
        
        return models.LoanResponse(
            loan_id=loan.loan_id,
            borrower_id=loan.borrower_id,
            lender_id=loan.lender_id,
            principal_amount=loan_terms['principal_amount'],
            interest_rate=loan_terms['interest_rate_apr'],
            term_months=loan_terms['term_months'],
            status=loan.status,
            balance_remaining=loan_terms['principal_amount'],  # Simplified - use principal
            next_payment_due=None,  # Can be calculated from repayment_schedule
            created_at=loan.created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}/loans/{loan_id}/payments", response_model=List[models.RepaymentResponse])
async def get_loan_payment_history(user_id: int, loan_id: int):
    """Get loan payment history"""
    session = db.get_session()
    try:
        # Check if loan exists and user has access
        loan = session.query(models.Loan).filter(
            models.Loan.loan_id == loan_id,
            (models.Loan.borrower_id == user_id) | (models.Loan.lender_id == user_id)
        ).first()
        
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found")
        
        payments = session.query(models.Repayment).filter(
            models.Repayment.loan_id == loan_id
        ).all()
        
        return [
            models.RepaymentResponse(
                repayment_id=payment.repayment_id,
                loan_id=payment.loan_id,
                amount=payment.amount,
                principal_portion=payment.principal_portion,
                interest_portion=payment.interest_portion,
                balance_after=payment.balance_after,
                payment_date=payment.payment_date,
                status=payment.status
            ) for payment in payments
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/users/{user_id}/loans/{loan_id}/payments", response_model=models.RepaymentResponse)
async def make_loan_payment(
    user_id: int,
    loan_id: int,
    payment_data: models.PaymentRequest
):
    """Make loan payment"""
    session = db.get_session()
    try:
        # Check if loan exists and user is the borrower
        loan = session.query(models.Loan).filter(
            models.Loan.loan_id == loan_id,
            models.Loan.borrower_id == user_id
        ).first()
        
        if not loan:
            raise HTTPException(status_code=404, detail="Loan not found or not authorized")
        
        # Status validation for payment processing
        if loan.status != 'active':
            raise HTTPException(status_code=400, detail="Can only make payments on active loans")
        
        # Check if source wallet account exists and belongs to user
        wallet = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == payment_data.origin_account_id,
            models.WalletAccount.account_holder_id == user_id
        ).first()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Source wallet account not found")
        
        if wallet.balance < payment_data.amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Calculate principal and interest portions (simplified)
        monthly_rate = loan.interest_rate / 100 / 12
        interest_portion = loan.balance_remaining * monthly_rate
        principal_portion = max(0, payment_data.amount - interest_portion)
        
        # Update loan balance
        loan.balance_remaining -= principal_portion
        
        # Update wallet balance
        wallet.balance -= payment_data.amount
        
        # Create repayment record
        new_payment = models.Repayment(
            loan_id=loan_id,
            amount=payment_data.amount,
            principal_portion=principal_portion,
            interest_portion=interest_portion,
            balance_after=loan.balance_remaining,
            status='completed'
        )
        
        session.add(new_payment)
        session.commit()
        session.refresh(new_payment)
        
        return models.RepaymentResponse(
            repayment_id=new_payment.repayment_id,
            loan_id=new_payment.loan_id,
            amount=new_payment.amount,
            principal_portion=new_payment.principal_portion,
            interest_portion=new_payment.interest_portion,
            balance_after=new_payment.balance_after,
            payment_date=new_payment.payment_date,
            status=new_payment.status
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# PORTFOLIO MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/users/{user_id}/portfolio/summary", response_model=models.PortfolioSummaryResponse)
async def get_portfolio_summary(user_id: int):
    """Get lender portfolio summary"""
    session = db.get_session()
    try:
        # Get all loans where user is lender - REFACTORED 3NF: JOIN with loan_offer
        loans_with_terms = session.query(
            models.Loan,
            models.LoanOffer.principal_amount,
            models.LoanOffer.interest_rate_apr
        ).join(
            models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id
        ).filter(models.Loan.lender_id == user_id).all()
        
        total_invested = sum(float(loan_with_terms[1]) for loan_with_terms in loans_with_terms)
        active_loans = len([lt for lt in loans_with_terms if lt[0].status == 'ACTIVE'])
        
        # Calculate total earned using actual interest rate from loan_offer
        total_earned = 0
        for loan_with_terms in loans_with_terms:
            loan = loan_with_terms[0]
            interest_rate = float(loan_with_terms[2]) / 100  # APR from loan_offer
            payments = session.query(models.Repayment).filter(models.Repayment.loan_id == loan.loan_id).all()
            total_earned += sum(float(payment.amount) * interest_rate for payment in payments)
        
        # Calculate default rate
        loans_only = [lt[0] for lt in loans_with_terms]
        defaulted_loans = len([loan for loan in loans_only if loan.status == 'DEFAULTED'])
        default_rate = defaulted_loans / len(loans_only) if loans_only else 0
        
        # Calculate average return (simplified)
        average_return = (total_earned / total_invested * 100) if total_invested > 0 else 0
        
        # Calculate pending payments (using principal amount from offer)
        pending_payments = sum(float(lt[1]) for lt in loans_with_terms if lt[0].status == 'ACTIVE')
        
        return models.PortfolioSummaryResponse(
            total_invested=total_invested,
            active_loans=active_loans,
            total_earned=total_earned,
            default_rate=default_rate,
            average_return=average_return,
            pending_payments=pending_payments
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}/portfolio/loans", response_model=models.TransactionHistoryResponse)
async def get_portfolio_loans(
    user_id: int,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get lender's loan portfolio"""
    session = db.get_session()
    try:
        # Get loans where user is lender
        query = session.query(models.Loan).filter(models.Loan.lender_id == user_id)
        
        if status:
            query = query.filter(models.Loan.status == status)
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        loans = query.offset((page - 1) * limit).limit(limit).all()
        
        loan_data = [
            models.LoanResponse(
                loan_id=loan.loan_id,
                borrower_id=loan.borrower_id,
                lender_id=loan.lender_id,
                principal_amount=loan.principal_amount,
                interest_rate=loan.interest_rate,
                term_months=loan.term_months,
                status=loan.status,
                balance_remaining=loan.balance_remaining,
                next_payment_due=loan.next_payment_due,
                created_at=loan.created_at
            ) for loan in loans
        ]
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return models.TransactionHistoryResponse(
            data=loan_data,
            pagination=pagination_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# AUTO-LENDING CONFIGURATION ENDPOINTS
# =============================================================================

@app.get("/users/{user_id}/auto-lending/config", response_model=models.AutoLendingConfigResponse)
async def get_auto_lending_config(user_id: int):
    """Get auto-lending configuration"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return models.AutoLendingConfigResponse(
            config_id=1,
            user_id=user_id,
            enabled=False,  # Default to disabled
            max_investment_per_loan=1000.00,  # Default values
            max_total_investment=10000.00,
            min_credit_grade="B",
            updated_at=datetime.datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.put("/users/{user_id}/auto-lending/config", response_model=models.AutoLendingConfigResponse)
async def update_auto_lending_config(
    user_id: int,
    config_data: models.UpdateAutoLendingConfigRequest
):
    """Update auto-lending configuration"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(
            models.UserAccount.user_id == user_id
        ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return models.AutoLendingConfigResponse(
            config_id=1,
            user_id=user_id,
            enabled=config_data.enabled,
            max_investment_per_loan=config_data.max_investment_per_loan or 1000.00,
            max_total_investment=config_data.max_total_investment or 10000.00,
            min_credit_grade=config_data.min_credit_grade or "B",
            updated_at=datetime.datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# RATING AND REVIEW ENDPOINTS  
# =============================================================================

@app.post("/users/{user_id}/ratings", response_model=models.CreateRatingResponse, tags=["Ratings & Reviews"], 
          summary="Submit a rating and review", 
          description="Submit a rating (1-5 stars) and optional comment for the micro-lending platform")
async def create_rating(
    rating_data: models.CreateRatingRequest,
    user_id: int = Path(..., description="ID of the user submitting the rating", example=123)
):
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate UUIDs for the other fields
        reviewee_id = int(str(uuid.uuid4()).replace('-', '')[:8], 16) % 1000000  # Convert UUID to int
        transaction_id = int(str(uuid.uuid4()).replace('-', '')[:8], 16) % 1000000  # Convert UUID to int
        
        # Create new rating using the updated database model (no reviewee_id FK)
        new_rating = models.RatingReview(
            reviewer_id=user_id,
            rating=rating_data.rating,
            comment=rating_data.comment
        )
        
        session.add(new_rating)
        session.commit()
        session.refresh(new_rating)
        
        return models.CreateRatingResponse(
            rating_id=new_rating.review_id,
            reviewee_id=reviewee_id  # Return the generated ID
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/ratings", response_model=List[models.RatingResponse], tags=["Ratings & Reviews"],
         summary="Get ratings",
         description="Get all ratings with optional user filter")
async def get_ratings(
    user_id: Optional[int] = Query(None, description="Optional user ID to filter ratings by")
):
    """Get ratings with optional user filter"""
    session = db.get_session()
    try:
        query = session.query(models.RatingReview)
        
        if user_id:
            # Filter by specific user
            query = query.filter(models.RatingReview.reviewer_id == user_id)
        
        ratings = query.order_by(models.RatingReview.created_at.desc()).all()
        print(f"Found {len(ratings)} ratings")
        print(ratings)

        return [
            models.RatingResponse(
                rating_id=rating.review_id,
                reviewer_id=rating.reviewer_id,
                rating=rating.rating,
                review_text=rating.comment or "",
                created_at=rating.created_at
            ) for rating in ratings
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# =============================================================================
# ADMIN DASHBOARD ENDPOINTS
# =============================================================================

@app.get("/admin/dashboard", response_model=models.AdminDashboardResponse)
async def get_admin_dashboard(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get admin dashboard data - ROLE PROTECTED"""
    session = db.get_session()
    try:
        # REFACTORED AUTH: Verify JWT and check ADMIN role
        payload = verify_token(credentials)
        user_id = payload.get("user_id")
        
        if not check_admin_role(session, user_id):
            raise HTTPException(status_code=403, detail="Admin access required")

        # Get total users
        total_users = session.query(models.UserAccount).count()
        
        # Get active loans
        active_loans = session.query(models.Loan).filter(models.Loan.status == 'active').count()
        
        # Get pending applications
        pending_applications = session.query(models.LoanApplication).filter(
            models.LoanApplication.status == 'pending'
        ).count()
        
        # Get total loan volume - REFACTORED 3NF: JOIN with loan_offer to get actual rates
        loans_with_terms = session.query(
            models.Loan,
            models.LoanOffer.principal_amount,
            models.LoanOffer.interest_rate_apr
        ).join(
            models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id
        ).all()
        
        total_loan_volume = sum(float(lt[1]) for lt in loans_with_terms)
        
        # Calculate revenue this month using actual interest rates from loan_offer
        from datetime import datetime, timedelta
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Join repayments with loans and offers to get actual interest rate
        revenue_this_month = 0.0
        for lt in loans_with_terms:
            loan = lt[0]
            interest_rate = float(lt[2]) / 100  # APR from loan_offer
            loan_payments = session.query(models.Repayment).filter(
                models.Repayment.loan_id == loan.loan_id,
                models.Repayment.created_at >= current_month_start
            ).all()
            revenue_this_month += sum(float(p.amount) * interest_rate for p in loan_payments)
        
        # Calculate default rate
        loans_only = [lt[0] for lt in loans_with_terms]
        total_loans = len(loans_only)
        defaulted_loans = len([loan for loan in loans_only if loan.status == 'DEFAULTED'])
        default_rate = defaulted_loans / total_loans if total_loans > 0 else 0
        
        compliance_issues = 3
        
        return models.AdminDashboardResponse(
            total_users=total_users,
            active_loans=active_loans,
            pending_applications=pending_applications,
            total_loan_volume=total_loan_volume,
            revenue_this_month=revenue_this_month,
            default_rate=default_rate,
            compliance_issues=compliance_issues
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# ADMIN LOAN MANAGEMENT ENDPOINTS
# =============================================================================

# =============================================================================
# ADMIN LOAN MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/admin/loans/approval")
async def get_loans_pending_approval(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get loans pending approval - ROLE PROTECTED"""
    session = db.get_session()
    try:
        # REFACTORED AUTH: Verify JWT and check ADMIN role
        payload = verify_token(credentials)
        user_id = payload.get("user_id")
        
        if not check_admin_role(session, user_id):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get applications pending review
        query = session.query(models.LoanApplication).filter(
            models.LoanApplication.status.in_(['under_review', 'pending','SUBMITTED'])
        )
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        applications = query.offset((page - 1) * limit).limit(limit).all()
        
        application_data = [
            models.LoanApplicationResponse(
                application_id=app.app_id,
                applicant_id=app.applicant_id,
                amount_requested=app.requested_amount,
                purpose=app.purpose,
                term_months=app.term_months,
                status=app.status,
                currency_code=app.currency_code,
                created_at=app.created_at,
                updated_at=app.created_at  # DB schema doesn't have updated_at, use created_at
            ) for app in applications
        ]
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return {
            "data": application_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/admin/loans/{loan_id}/approve", response_model=models.LoanApplicationResponse)
async def approve_loan_application(
    loan_id: int,
    approval_data: models.AdminLoanApprovalRequest
):
    """Manually approve loan application"""
    session = db.get_session()
    try:
        # Find the loan application
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == loan_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        if application.status not in ['pending', 'under_review',"SUBMITTED"]:
            raise HTTPException(status_code=400, detail="Can only approve pending applications")
        
        # Update application status
        application.status = 'approved'
        
        # Create audit log entry
        audit_log = models.AuditLog(
            actor_id=1,  # This should be from JWT token in real implementation
            action='loan_approval',
            entity_type='loan_application',
            entity_id=loan_id,
            old_values_json={"status": application.status},
            new_values_json={"status": "approved", "notes": approval_data.notes, "conditions": approval_data.conditions}
        )
        session.add(audit_log)
        
        session.commit()
        session.refresh(application)
        
        return models.LoanApplicationResponse(
            application_id=application.app_id,
            applicant_id=application.applicant_id,
            amount_requested=application.requested_amount,
            purpose=application.purpose,
            term_months=application.term_months,
            status=application.status,
            currency_code=application.currency_code,
            created_at=application.created_at,
            updated_at=application.created_at  # DB schema doesn't have updated_at, use created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/admin/loans/{loan_id}/reject", response_model=models.LoanApplicationResponse)
async def reject_loan_application(
    loan_id: int,
    rejection_data: models.AdminLoanRejectionRequest
):
    """Reject loan application"""
    session = db.get_session()
    try:
        # Find the loan application
        application = session.query(models.LoanApplication).filter(
            models.LoanApplication.app_id == loan_id
        ).first()
        
        if not application:
            raise HTTPException(status_code=404, detail="Loan application not found")
        
        if application.status not in ['pending', 'under_review']:
            raise HTTPException(status_code=400, detail="Can only reject pending applications")
        
        # Update application status
        application.status = 'rejected'
        
        # Create audit log entry
        audit_log = models.AuditLog(
            actor_id=1,  # Using default actor_id for demo; would extract from JWT in full implementation
            action='loan_rejection',
            entity_type='loan_application',
            entity_id=loan_id,
            old_values_json={"status": application.status},
            new_values_json={"status": "rejected", "reason": rejection_data.reason, "notes": rejection_data.notes}
        )
        session.add(audit_log)
        
        session.commit()
        session.refresh(application)
        
        return models.LoanApplicationResponse(
            application_id=application.app_id,
            applicant_id=application.applicant_id,
            amount_requested=application.requested_amount,
            purpose=application.purpose,
            term_months=application.term_months,
            status=application.status,
            currency_code=application.currency_code,
            created_at=application.created_at,
            updated_at=application.created_at  # DB schema doesn't have updated_at, use created_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# ADMIN COMPLIANCE ENDPOINTS
# =============================================================================

@app.get("/admin/fraud-alerts", response_model=List[models.FraudAlertResponse])
async def get_fraud_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None
):
    """Get fraud detection alerts"""
    from datetime import datetime
    return [
        models.FraudAlertResponse(
            alert_id=1,
            user_id=123,
            alert_type="suspicious_activity",
            severity="high",
            status="open",
            description="Multiple loan applications from same IP",
            created_at=datetime.utcnow()
        )
    ]

@app.get("/admin/audit-logs", response_model=List[models.AuditLogResponse])
async def get_audit_logs(
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get audit trail logs"""
    session = db.get_session()
    try:
        query = session.query(models.AuditLog)
        
        if actor_id:
            query = query.filter(models.AuditLog.actor_id == actor_id)
        if action:
            query = query.filter(models.AuditLog.action == action)
        if entity_type:
            query = query.filter(models.AuditLog.entity_type == entity_type)
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        logs = query.offset((page - 1) * limit).limit(limit).all()
        
        log_data = [
            models.AuditLogResponse(
                log_id=log.audit_id,
                actor_id=log.actor_id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                details=None,  # No details field in model
                timestamp=log.created_at
            ) for log in logs
        ]
        
        return log_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# REPORTING ENDPOINTS
# =============================================================================

@app.get("/reports/platform-metrics", response_model=models.PlatformMetricsResponse)
async def get_platform_metrics(
    period: str = Query("monthly", regex="^(daily|weekly|monthly|quarterly|yearly)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Get platform performance metrics"""
    session = db.get_session()
    try:
        from datetime import datetime, timedelta
        
        # Set default date range based on period
        if not date_from or not date_to:
            now = datetime.now()
            if period == "monthly":
                date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                date_to = now
            elif period == "quarterly":
                quarter_start = now.replace(month=((now.month-1)//3)*3+1, day=1, hour=0, minute=0, second=0, microsecond=0)
                date_from = quarter_start
                date_to = now
            else:
                date_from = now - timedelta(days=30)
                date_to = now
        else:
            date_from = datetime.fromisoformat(date_from)
            date_to = datetime.fromisoformat(date_to)
        
        # Get loans originated in period - REFACTORED 3NF: JOIN with loan_offer
        loans_with_terms = session.query(
            models.Loan,
            models.LoanOffer.principal_amount
        ).join(
            models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id
        ).filter(
            models.Loan.start_date >= date_from,
            models.Loan.start_date <= date_to
        ).all()
        
        total_loans_originated = len(loans_with_terms)
        total_loan_volume = sum(float(lt[1]) for lt in loans_with_terms) if loans_with_terms else 0
        average_loan_size = total_loan_volume / total_loans_originated if total_loans_originated > 0 else 0
        
        # Calculate default rate - include interest_rate_apr for revenue calculation
        all_loans_with_terms = session.query(
            models.Loan,
            models.LoanOffer.principal_amount,
            models.LoanOffer.interest_rate_apr
        ).join(
            models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id
        ).all()
        
        all_loans = [lt[0] for lt in all_loans_with_terms]
        defaulted_loans = len([loan for loan in all_loans if loan.status == 'DEFAULTED'])
        default_rate = defaulted_loans / len(all_loans) if all_loans else 0
        
        # Calculate revenue using actual interest rates from loan_offer
        payments_in_period = session.query(models.Repayment).filter(
            models.Repayment.created_at >= date_from,
            models.Repayment.created_at <= date_to
        ).all()
        
        # Build loan_id to interest_rate mapping
        loan_rates = {lt[0].loan_id: float(lt[2]) / 100 for lt in all_loans_with_terms}
        revenue_generated = sum(
            float(payment.amount) * loan_rates.get(payment.loan_id, 0.0) 
            for payment in payments_in_period
        )
        
        # Get user metrics
        active_users = session.query(models.UserAccount).filter(
            models.UserAccount.status == 'active'
        ).count()
        
        new_registrations = session.query(models.UserAccount).filter(
            models.UserAccount.created_at >= date_from,
            models.UserAccount.created_at <= date_to
        ).count()
        
        return models.PlatformMetricsResponse(
            reporting_period=f"{date_from.strftime('%Y-%m')}",
            total_loans_originated=total_loans_originated,
            total_loan_volume=total_loan_volume,
            average_loan_size=average_loan_size,
            default_rate=default_rate,
            revenue_generated=revenue_generated,
            active_users=active_users,
            new_registrations=new_registrations
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/reports/revenue", response_model=models.RevenueReportResponse)
async def generate_revenue_report(
    breakdown_by: str = Query("month", regex="^(month|quarter|year|product_type|geography)$")
):
    """Generate revenue reports"""
    session = db.get_session()
    try:
        from datetime import datetime, timedelta
        
        # Get last 12 months of data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Get all loans with their interest rates for revenue calculation
        all_loans_with_rates = session.query(
            models.Loan,
            models.LoanOffer.interest_rate_apr,
            models.LoanOffer.fees_percent
        ).join(
            models.LoanOffer, models.Loan.offer_id == models.LoanOffer.offer_id
        ).all()
        
        # Build loan_id to rates mapping
        loan_rates = {lt[0].loan_id: float(lt[1]) / 100 for lt in all_loans_with_rates}
        loan_fees = {lt[0].loan_id: float(lt[2] or 0) / 100 for lt in all_loans_with_rates}
        
        payments = session.query(models.Repayment).filter(
            models.Repayment.created_at >= start_date,
            models.Repayment.created_at <= end_date
        ).all()
        
        # Calculate totals using actual interest rates from loan_offer
        interest_revenue = sum(
            float(payment.amount) * loan_rates.get(payment.loan_id, 0.0)
            for payment in payments
        )
        fee_revenue = sum(
            float(payment.amount) * loan_fees.get(payment.loan_id, 0.0)
            for payment in payments
        )
        total_revenue = interest_revenue + fee_revenue
        
        # Create breakdown data using actual rates
        breakdown_data = []
        if breakdown_by == "month":
            for i in range(12):
                month_start = start_date + timedelta(days=30*i)
                month_end = start_date + timedelta(days=30*(i+1))
                month_payments = [p for p in payments if month_start <= p.created_at < month_end]
                month_revenue = sum(
                    float(p.amount) * loan_rates.get(p.loan_id, 0.0)
                    for p in month_payments
                )
                breakdown_data.append({
                    "period": month_start.strftime('%Y-%m'),
                    "revenue": month_revenue
                })
        
        return models.RevenueReportResponse(
            reporting_period=f"{start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')}",
            breakdown_by=breakdown_by,
            total_revenue=total_revenue,
            fee_revenue=fee_revenue,
            interest_revenue=interest_revenue,
            breakdown_data=breakdown_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# ADMIN RISK MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/admin/delinquency", response_model=models.TransactionHistoryResponse)
async def get_delinquency_reports(
    days_past_due: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get delinquency reports"""
    session = db.get_session()
    try:
        from datetime import datetime, timedelta
        
        # Get loans that are past due
        current_date = datetime.now().date()
        
        # Get loans that have missed payments by joining with repayment schedule
        query = session.query(models.Loan).join(
            models.RepaymentSchedule, models.Loan.loan_id == models.RepaymentSchedule.loan_id
        ).filter(
            models.Loan.status == 'ACTIVE',
            models.RepaymentSchedule.status.in_(['PENDING', 'PARTIAL']),
            models.RepaymentSchedule.due_date < current_date
        ).distinct()
        
        # Filter by days past due if specified
        if days_past_due is not None:
            cutoff_date = current_date - timedelta(days=days_past_due)
            query = query.filter(models.RepaymentSchedule.due_date <= cutoff_date)
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        loans = query.offset((page - 1) * limit).limit(limit).all()
        
        delinquency_data = []
        for loan in loans:
            # Get borrower info
            borrower = session.query(models.UserAccount).filter(
                models.UserAccount.user_id == loan.borrower_id
            ).first()
            
            # Get the overdue repayment schedule for this loan
            overdue_schedule = session.query(models.RepaymentSchedule).filter(
                models.RepaymentSchedule.loan_id == loan.loan_id,
                models.RepaymentSchedule.status.in_(['PENDING', 'PARTIAL']),
                models.RepaymentSchedule.due_date < current_date
            ).order_by(models.RepaymentSchedule.due_date.asc()).first()
            
            # Calculate days past due
            days_overdue = (current_date - overdue_schedule.due_date).days if overdue_schedule else 0
            
            # Get last payment
            last_payment = session.query(models.Repayment).filter(
                models.Repayment.loan_id == loan.loan_id
            ).order_by(models.Repayment.created_at.desc()).first()
            
            # Determine risk level based on days overdue
            if days_overdue >= 90:
                risk_level = "high"
            elif days_overdue >= 30:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            delinquency_data.append(
                models.DelinquencyReportResponse(
                    loan_id=loan.loan_id,
                    borrower_id=loan.borrower_id,
                    borrower_name=f"{borrower.name_first} {borrower.name_last}" if borrower else "Unknown",
                    loan_amount=loan.principal_amount,
                    balance_remaining=loan.principal_amount,  # Simplified - use principal amount
                    days_past_due=days_overdue,
                    last_payment_date=last_payment.created_at if last_payment else None,
                    next_payment_due=overdue_schedule.due_date if overdue_schedule else loan.maturity_date,
                    risk_level=risk_level
                )
            )
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return models.TransactionHistoryResponse(
            data=delinquency_data,
            pagination=pagination_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# ADMIN FINANCIAL OPERATIONS ENDPOINTS
# =============================================================================

@app.get("/admin/transactions", response_model=models.TransactionHistoryResponse)
async def monitor_platform_transactions(
    transaction_type: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Monitor all platform transactions"""
    session = db.get_session()
    try:
        from datetime import datetime
        
        # Build query
        query = session.query(models.TransactionLedger)
        
        # Filter by transaction type
        if transaction_type:
            query = query.filter(models.TransactionLedger.related_type == transaction_type.upper())
        
        # Filter by amount range
        if amount_min is not None:
            query = query.filter(models.TransactionLedger.amount >= amount_min)
        if amount_max is not None:
            query = query.filter(models.TransactionLedger.amount <= amount_max)
        
        # Filter by date range
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from)
            query = query.filter(models.TransactionLedger.created_at >= date_from_obj)
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to)
            query = query.filter(models.TransactionLedger.created_at <= date_to_obj)
        
        # Order by most recent first
        query = query.order_by(models.TransactionLedger.created_at.desc())
        
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        transactions = query.offset((page - 1) * limit).limit(limit).all()
        
        transaction_data = []
        for tx in transactions:
            # Get user info from wallet account
            wallet = session.query(models.WalletAccount).filter(
                models.WalletAccount.account_id == tx.account_id
            ).first()
            
            user = None
            if wallet:
                user = session.query(models.UserAccount).filter(
                    models.UserAccount.user_id == wallet.owner_id
                ).first()
            
            transaction_data.append(
                models.AdminTransactionResponse(
                    tx_id=tx.tx_id,
                    related_type=tx.related_type,
                    related_id=tx.related_id,
                    account_id=tx.account_id,
                    user_id=wallet.account_holder_id if wallet else 0,
                    user_name=f"{user.first_name} {user.last_name}" if user else "Unknown",
                    direction=tx.direction,
                    amount=tx.amount,
                    currency_code=tx.currency_code,
                    memo=tx.memo,
                    posted_by=tx.posted_by,
                    created_at=tx.created_at,
                    status="completed"  # Simplified status
                )
            )
        
        pagination_info = models.PaginationInfo(
            page=page,
            limit=limit,
            total_pages=total_pages,
            total_count=total_count,
            has_next=page < total_pages,
            has_prev=page > 1
        )
        
        return models.TransactionHistoryResponse(
            data=transaction_data,
            pagination=pagination_info
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# =============================================================================
# DEMO ENDPOINTS - Transaction Handling & Database Administration
# =============================================================================

class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    memo: Optional[str] = None

class DemoResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    audit_log_id: Optional[int] = None

@app.post("/demo/transaction/success", response_model=DemoResponse, tags=["Demo"])
async def demo_successful_transaction(transfer: TransferRequest):
    """
    Demonstrates a successful atomic transaction with:
    - Balance validation
    - Atomic debit/credit operations
    - Transaction ledger entries
    - Audit logging
    """
    session = models.Database().get_session()
    
    try:
        print("🔄 DEMO: Starting transaction...")
        
        # Step 1: Validate accounts exist
        from_account = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == transfer.from_account_id
        ).with_for_update().first()
        
        to_account = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == transfer.to_account_id
        ).with_for_update().first()
        
        if not from_account or not to_account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Step 2: Validate sufficient balance
        if from_account.available_balance < Decimal(str(transfer.amount)):
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Step 3: Update balances (ATOMIC OPERATION)
        from_account.available_balance -= Decimal(str(transfer.amount))
        to_account.available_balance += Decimal(str(transfer.amount))
        
        # Step 4: Record in transaction ledger (double-entry bookkeeping)
        debit_entry = models.TransactionLedger(
            related_type='ADJUSTMENT',
            account_id=transfer.from_account_id,
            direction='DEBIT',
            amount=Decimal(str(transfer.amount)),
            currency_code=from_account.currency_code,
            memo=f"Transfer to account {transfer.to_account_id}: {transfer.memo or 'N/A'}"
        )
        
        credit_entry = models.TransactionLedger(
            related_type='ADJUSTMENT',
            account_id=transfer.to_account_id,
            direction='CREDIT',
            amount=Decimal(str(transfer.amount)),
            currency_code=to_account.currency_code,
            memo=f"Transfer from account {transfer.from_account_id}: {transfer.memo or 'N/A'}"
        )
        
        session.add(debit_entry)
        session.add(credit_entry)
        
        # Step 5: Create audit log entry
        audit_entry = models.AuditLog(
            actor_id=None,
            action='TRANSFER',
            entity_type='wallet_account',
            entity_id=transfer.from_account_id,
            old_values_json={'balance': float(from_account.available_balance + Decimal(str(transfer.amount)))},
            new_values_json={'balance': float(from_account.available_balance)}
        )
        session.add(audit_entry)
        session.flush()
        
        # Step 6: COMMIT TRANSACTION
        session.commit()
        
        print("✅ DEMO: Transaction committed successfully")
        
        return DemoResponse(
            success=True,
            message=f"Successfully transferred ${transfer.amount} from account {transfer.from_account_id} to {transfer.to_account_id}",
            data={
                "from_account_balance": float(from_account.available_balance),
                "to_account_balance": float(to_account.available_balance),
                "debit_tx_id": debit_entry.tx_id,
                "credit_tx_id": credit_entry.tx_id
            },
            audit_log_id=audit_entry.audit_id
        )
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        print(f"❌ DEMO: Transaction rolled back due to error: {e}")
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
    finally:
        session.close()

@app.post("/demo/transaction/failure", response_model=DemoResponse, tags=["Demo"])
async def demo_failed_transaction(transfer: TransferRequest):
    """
    Demonstrates transaction rollback on error:
    - Validates accounts
    - Detects insufficient balance
    - Rolls back all changes
    - Logs failure in audit
    """
    session = models.Database().get_session()
    
    try:
        print("🔄 DEMO: Starting transaction (will fail)...")
        
        from_account = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == transfer.from_account_id
        ).with_for_update().first()
        
        if not from_account:
            raise HTTPException(status_code=404, detail="Source account not found")
        
        original_balance = from_account.available_balance
        
        if from_account.available_balance < Decimal(str(transfer.amount)):
            audit_entry = models.AuditLog(
                actor_id=None,
                action='TRANSFER_FAILED',
                entity_type='wallet_account',
                entity_id=transfer.from_account_id,
                old_values_json={'balance': float(original_balance), 'attempted_amount': transfer.amount},
                new_values_json={'reason': 'insufficient_balance'}
            )
            session.add(audit_entry)
            session.commit()
            
            print("❌ DEMO: Transaction rolled back - insufficient balance")
            
            return DemoResponse(
                success=False,
                message=f"Transfer failed: Insufficient balance (has ${original_balance}, needs ${transfer.amount})",
                data={
                    "current_balance": float(original_balance),
                    "required_balance": transfer.amount,
                    "deficit": transfer.amount - float(original_balance)
                },
                audit_log_id=audit_entry.audit_id
            )
        
        session.rollback()
        return DemoResponse(
            success=False,
            message="Demo failed: Account has sufficient balance",
            data=None
        )
        
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        print(f"❌ DEMO: Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/demo/query/explain", tags=["Demo"])
async def demo_explain_plan(query_type: str = "loan_by_borrower"):
    """
    Demonstrates query performance optimization with EXPLAIN plans
    Shows index usage and query optimization
    """
    session = models.Database().get_session()
    
    try:
        explain_results = []
        
        if query_type == "loan_by_borrower":
            query_sql = "SELECT * FROM loan WHERE borrower_id = 123"
            explain_sql = f"EXPLAIN {query_sql}"
        elif query_type == "payments_due":
            query_sql = "SELECT * FROM repayment_schedule WHERE due_date <= CURDATE() AND status = 'PENDING'"
            explain_sql = f"EXPLAIN {query_sql}"
        elif query_type == "account_transactions":
            query_sql = "SELECT * FROM transaction_ledger WHERE account_id = 456 ORDER BY created_at DESC LIMIT 50"
            explain_sql = f"EXPLAIN {query_sql}"
        elif query_type == "audit_trail":
            query_sql = "SELECT * FROM audit_log WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            explain_sql = f"EXPLAIN {query_sql}"
        else:
            raise HTTPException(status_code=400, detail="Invalid query type")
        
        result = session.execute(text(explain_sql))
        
        for row in result:
            explain_results.append({
                "id": row[0],
                "select_type": row[1],
                "table": row[2],
                "type": row[3],
                "possible_keys": row[4],
                "key": row[5],
                "key_len": row[6],
                "ref": row[7],
                "rows": row[8],
                "Extra": row[9]
            })
        
        return {
            "query": query_sql,
            "explain_plan": explain_results,
            "analysis": {
                "using_index": any(r["key"] is not None for r in explain_results),
                "index_used": explain_results[0]["key"] if explain_results else None,
                "estimated_rows": explain_results[0]["rows"] if explain_results else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/demo/audit/trail", tags=["Demo"])
async def demo_audit_trail(entity_type: str = "wallet_account", limit: int = 10):
    """
    Demonstrates audit logging and trail querying
    Shows all changes to specified entity type
    """
    session = models.Database().get_session()
    
    try:
        audit_logs = session.query(models.AuditLog).filter(
            models.AuditLog.entity_type == entity_type
        ).order_by(models.AuditLog.created_at.desc()).limit(limit).all()
        
        return {
            "entity_type": entity_type,
            "total_logs": len(audit_logs),
            "logs": [
                {
                    "audit_id": log.audit_id,
                    "actor_id": log.actor_id,
                    "action": log.action,
                    "entity_id": log.entity_id,
                    "old_values": log.old_values_json,
                    "new_values": log.new_values_json,
                    "timestamp": log.created_at.isoformat() if log.created_at else None
                }
                for log in audit_logs
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/demo/constraint/violation", tags=["Demo"])
async def demo_constraint_violation(violation_type: str = "negative_balance"):
    """
    Demonstrates database constraint enforcement
    Shows how CHECK constraints prevent invalid data
    """
    session = models.Database().get_session()
    
    try:
        if violation_type == "negative_balance":
            invalid_account = models.WalletAccount(
                owner_type='USER',
                owner_id=9999,
                currency_code='USD',
                available_balance=Decimal('-100.00'),
                status='active'
            )
            session.add(invalid_account)
            session.commit()
            
        elif violation_type == "zero_principal":
            invalid_offer = models.LoanOffer(
                app_id=1,
                lender_type='USER',
                lender_id=1,
                principal_amount=Decimal('0.00'),
                currency_code='USD',
                interest_rate_apr=Decimal('5.5'),
                repayment_type='AMORTIZING',
                term_months=12,
                status='PENDING'
            )
            session.add(invalid_offer)
            session.commit()
            
        return DemoResponse(
            success=False,
            message="Constraint should have been violated, but wasn't!",
            data=None
        )
        
    except IntegrityError as e:
        session.rollback()
        return DemoResponse(
            success=True,
            message=f"✅ Constraint successfully prevented invalid data: {str(e.orig)}",
            data={"violation_type": violation_type}
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# =============================================================================
# CACHE & REFERENCE DATA ENDPOINTS
# =============================================================================

# Cache TTL loaded from environment variable for configurability
REFERENCE_TTL = int(os.getenv('CACHE_REFERENCE_TTL', 3600))  # 1 hour default
TRANSACTION_TTL = int(os.getenv('CACHE_TRANSACTION_TTL', 300))  # 5 minutes default

class ReferenceDataResponse(BaseModel):
    type: str
    data: List[Dict[str, Any]]
    cached: bool
    ttl: Optional[int] = None
    latency_ms: Optional[float] = None

@app.get("/cache/reference/{ref_type}", response_model=ReferenceDataResponse)
async def get_reference_data(ref_type: str):
    """Get cached reference data (currencies, loan_types, regions, credit_tiers)
    
    Data is loaded from database reference tables on cache miss, demonstrating
    the cache-aside pattern with actual database integration.
    """
    import time
    start_time = time.time()
    
    valid_types = ['currencies', 'loan_types', 'regions', 'credit_tiers', 'loan_statuses']
    if ref_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {valid_types}")
    
    redis = get_redis_client()
    metrics = get_cache_metrics()
    cache_key = f"ml:reference:{ref_type}"
    
    cached_data = redis.get_json(cache_key)
    if cached_data:
        latency_ms = (time.time() - start_time) * 1000
        ttl = redis.ttl(cache_key)
        # Record cache hit with latency
        if metrics:
            metrics.record_hit(operation=f'reference:{ref_type}', latency_ms=latency_ms)
        logging.getLogger("cache").info(f"HIT {cache_key} ttl={ttl}s in {latency_ms:.2f}ms")
        return ReferenceDataResponse(type=ref_type, data=cached_data, cached=True, ttl=ttl, latency_ms=round(latency_ms, 2))
    
    # Cache miss - load from database reference tables
    data = []
    session = db.get_session()
    try:
        if ref_type == 'currencies':
            # Load from ref_currency table
            result = session.execute(text("""
                SELECT currency_code as code, currency_name as name, symbol
                FROM ref_currency WHERE is_active = TRUE
            """))
            data = [dict(row._mapping) for row in result.fetchall()]
        elif ref_type == 'loan_types':
            # Load from ref_loan_product table
            result = session.execute(text("""
                SELECT product_code as code, product_name as name, 
                       min_amount, max_amount, base_interest_rate as base_rate, category
                FROM ref_loan_product WHERE is_active = TRUE
            """))
            data = [dict(row._mapping) for row in result.fetchall()]
            # Convert Decimal to float for JSON
            for item in data:
                for key in ['min_amount', 'max_amount', 'base_rate']:
                    if key in item and item[key] is not None:
                        item[key] = float(item[key])
        elif ref_type == 'regions':
            # Load from ref_region table
            result = session.execute(text("""
                SELECT region_code as code, region_name as name, region_type, timezone
                FROM ref_region WHERE is_active = TRUE
            """))
            data = [dict(row._mapping) for row in result.fetchall()]
        elif ref_type == 'credit_tiers':
            # Load from ref_credit_tier table
            result = session.execute(text("""
                SELECT tier_code as code, tier_name as name, 
                       min_score, max_score, risk_weight as rate_adjustment
                FROM ref_credit_tier
            """))
            data = [dict(row._mapping) for row in result.fetchall()]
            # Convert Decimal to float
            for item in data:
                if 'rate_adjustment' in item and item['rate_adjustment'] is not None:
                    item['rate_adjustment'] = float(item['rate_adjustment'])
        elif ref_type == 'loan_statuses':
            # Load from dim_loan_status table
            result = session.execute(text("SELECT status_code, status_name FROM dim_loan_status ORDER BY status_key"))
            data = [{'code': row[0], 'name': row[1]} for row in result]
    except Exception as e:
        # Log error and return empty list
        import logging
        logging.error(f"Failed to load reference data '{ref_type}' from database: {e}")
        data = []
    finally:
        session.close()
    
    latency_ms = (time.time() - start_time) * 1000
    redis.set_json(cache_key, data, REFERENCE_TTL)
    # Record cache miss with DB latency
    if metrics:
        metrics.record_miss(operation=f'reference:{ref_type}', latency_ms=latency_ms)
    logging.getLogger("cache").info(f"MISS {cache_key} loaded from DB in {latency_ms:.2f}ms ttl={REFERENCE_TTL}s")
    return ReferenceDataResponse(type=ref_type, data=data, cached=False, ttl=REFERENCE_TTL, latency_ms=round(latency_ms, 2))

@app.delete("/cache/reference/{ref_type}")
async def invalidate_reference_cache(ref_type: str):
    """Invalidate reference data cache"""
    redis = get_redis_client()
    metrics = get_cache_metrics()
    if ref_type == 'all':
        ref_keys = redis.keys('ml:reference:*')
        tx_keys = redis.keys('ml:transactions:*')
        all_keys = (ref_keys or []) + (tx_keys or [])
        if all_keys:
            for k in all_keys:
                redis.delete(k)
        # Record invalidation
        if metrics:
            metrics.record_invalidation(operation='reference:all', keys_invalidated=len(all_keys))
        return {"invalidated": len(all_keys)}
    
    cache_key = f"ml:reference:{ref_type}"
    deleted = redis.delete(cache_key)
    # Record invalidation
    if metrics and deleted > 0:
        metrics.record_invalidation(operation=f'reference:{ref_type}', keys_invalidated=deleted)
    return {"invalidated": deleted}


# =============================================================================
# CACHE METRICS ENDPOINTS
# =============================================================================

class CacheMetricsResponse(BaseModel):
    timestamp: str
    minute_key: str
    current_minute: Dict[str, Any]
    totals: Dict[str, Any]
    latency: Dict[str, Any]
    errors_per_minute: int

class HourlyMetricsResponse(BaseModel):
    hours: int
    data: List[Dict[str, Any]]

@app.get("/cache/metrics", response_model=CacheMetricsResponse)
async def get_cache_metrics_endpoint():
    """Get current cache metrics (hits, misses, latency, error rates)"""
    metrics = get_cache_metrics()
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics not available")
    return metrics.get_current_stats()

@app.get("/cache/metrics/hourly", response_model=HourlyMetricsResponse)
async def get_hourly_metrics(hours: int = Query(24, ge=1, le=168)):
    """Get hourly cache metrics for the last N hours"""
    metrics = get_cache_metrics()
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics not available")
    return {"hours": hours, "data": metrics.get_hourly_stats(hours)}

@app.delete("/cache/metrics")
async def reset_cache_metrics():
    """Reset all cache metrics (for testing)"""
    metrics = get_cache_metrics()
    if not metrics:
        raise HTTPException(status_code=503, detail="Metrics not available")
    deleted = metrics.reset_metrics()
    return {"reset": True, "keys_deleted": deleted}


# =============================================================================
# REPORTING & ANALYTICS ENDPOINTS
# =============================================================================

class TransactionRow(BaseModel):
    loan_id: int
    borrower_id: int
    borrower_email: str
    principal_amount: float
    interest_rate: float
    status: str
    created_at: str
    term_months: int

class PaginatedTransactionsResponse(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int
    data: List[TransactionRow]
    cached: bool
    has_next: bool
    has_prev: bool
    latency_ms: Optional[float] = None

@app.get("/reporting/transactions", response_model=PaginatedTransactionsResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    status: Optional[str] = None,
    borrower_id: Optional[int] = None
):
    """Get paginated loan transactions with caching and look-ahead"""
    import time
    start_time = time.time()
    
    redis = get_redis_client()
    metrics = get_cache_metrics()
    cache_key = f"ml:transactions:p{page}:s{page_size}:st{status or 'all'}:b{borrower_id or 'all'}"
    
    cached_data = redis.get_json(cache_key)
    if cached_data:
        latency_ms = (time.time() - start_time) * 1000
        cached_data['cached'] = True
        cached_data['latency_ms'] = round(latency_ms, 2)
        # Record cache hit
        if metrics:
            metrics.record_hit(operation='transactions', latency_ms=latency_ms)
        logging.getLogger("cache").info(f"HIT {cache_key} in {latency_ms:.2f}ms")
        return PaginatedTransactionsResponse(**cached_data)
    
    session = db.get_session()
    try:
        count_query = "SELECT COUNT(*) FROM loan l JOIN user u ON l.borrower_id = u.id"
        data_query = """
            SELECT l.id, l.borrower_id, u.email, l.principal_amount, l.interest_rate,
                   l.status, l.created_at, l.term_months
            FROM loan l
            JOIN user u ON l.borrower_id = u.id
        """
        
        where_clauses = []
        params = {}
        if status:
            where_clauses.append("l.status = :status")
            params['status'] = status
        if borrower_id:
            where_clauses.append("l.borrower_id = :borrower_id")
            params['borrower_id'] = borrower_id
        
        if where_clauses:
            where_str = " WHERE " + " AND ".join(where_clauses)
            count_query += where_str
            data_query += where_str
        
        data_query += " ORDER BY l.created_at DESC LIMIT :limit OFFSET :offset"
        params['limit'] = page_size
        params['offset'] = (page - 1) * page_size
        
        count_result = session.execute(text(count_query), params).scalar()
        total_count = count_result or 0
        total_pages = (total_count + page_size - 1) // page_size
        
        result = session.execute(text(data_query), params)
        rows = []
        for r in result:
            rows.append(TransactionRow(
                loan_id=r[0],
                borrower_id=r[1],
                borrower_email=r[2],
                principal_amount=float(r[3]),
                interest_rate=float(r[4]),
                status=r[5],
                created_at=r[6].isoformat() if r[6] else '',
                term_months=r[7]
            ))
        
        response_data = {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': total_pages,
            'data': [r.model_dump() for r in rows],
            'cached': False,
            'has_next': page < total_pages,
            'has_prev': page > 1,
            'latency_ms': round((time.time() - start_time) * 1000, 2)
        }
        
        # Record cache miss with DB latency
        if metrics:
            metrics.record_miss(operation='transactions', latency_ms=response_data['latency_ms'])
        logging.getLogger("cache").info(f"MISS {cache_key} loaded from DB in {response_data['latency_ms']:.2f}ms ttl=300s")
        
        redis.set_json(cache_key, response_data, 300)
        
        if page < total_pages:
            next_page = page + 1
            next_cache_key = f"ml:transactions:p{next_page}:s{page_size}:st{status or 'all'}:b{borrower_id or 'all'}"
            if not redis.exists(next_cache_key):
                next_offset = (next_page - 1) * page_size
                next_params = dict(params)
                next_params['offset'] = next_offset
                next_result = session.execute(text(data_query), next_params)
                next_rows = []
                for r in next_result:
                    next_rows.append({
                        'loan_id': r[0],
                        'borrower_id': r[1],
                        'borrower_email': r[2],
                        'principal_amount': float(r[3]),
                        'interest_rate': float(r[4]),
                        'status': r[5],
                        'created_at': r[6].isoformat() if r[6] else '',
                        'term_months': r[7]
                    })
                next_data = {
                    'page': next_page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'data': next_rows,
                    'cached': False,
                    'has_next': next_page < total_pages,
                    'has_prev': True
                }
                redis.set_json(next_cache_key, next_data, 300)
        
        if page < total_pages:
            next_key = f"ml:transactions:p{page+1}:s{page_size}:st{status or 'all'}:b{borrower_id or 'all'}"
            if not redis.exists(next_key):
                next_params = params.copy()
                next_params['offset'] = page * page_size
                next_result = session.execute(text(data_query.replace(f"OFFSET :offset", f"OFFSET {page * page_size}")), next_params)
                next_rows = []
                for r in next_result:
                    next_rows.append({
                        'loan_id': r[0], 'borrower_id': r[1], 'borrower_email': r[2],
                        'principal_amount': float(r[3]), 'interest_rate': float(r[4]),
                        'status': r[5], 'created_at': r[6].isoformat() if r[6] else '', 'term_months': r[7]
                    })
                next_data = {
                    'page': page + 1, 'page_size': page_size, 'total_count': total_count,
                    'total_pages': total_pages, 'data': next_rows, 'cached': False,
                    'has_next': (page + 1) < total_pages, 'has_prev': True
                }
                redis.set_json(next_key, next_data, 300)
        
        return PaginatedTransactionsResponse(**response_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

class AnalyticsSummary(BaseModel):
    total_loans: int
    total_principal: float
    active_loans: int
    defaulted_loans: int
    avg_interest_rate: float
    total_borrowers: int

@app.get("/reporting/summary", response_model=AnalyticsSummary)
async def get_analytics_summary():
    """Get analytics summary with caching"""
    redis = get_redis_client()
    cache_key = "ml:analytics:summary"
    
    cached = redis.get_json(cache_key)
    if cached:
        return AnalyticsSummary(**cached)
    
    session = db.get_session()
    try:
        result = session.execute(text("""
            SELECT 
                COUNT(DISTINCT l.id) as total_loans,
                COALESCE(SUM(l.principal_amount), 0) as total_principal,
                SUM(CASE WHEN l.status = 'active' THEN 1 ELSE 0 END) as active_loans,
                SUM(CASE WHEN l.status = 'defaulted' THEN 1 ELSE 0 END) as defaulted_loans,
                COALESCE(AVG(l.interest_rate), 0) as avg_interest_rate,
                COUNT(DISTINCT l.borrower_id) as total_borrowers
            FROM loan l
        """)).first()
        
        summary = AnalyticsSummary(
            total_loans=result[0] or 0,
            total_principal=float(result[1] or 0),
            active_loans=result[2] or 0,
            defaulted_loans=result[3] or 0,
            avg_interest_rate=float(result[4] or 0),
            total_borrowers=result[5] or 0
        )
        
        redis.set_json(cache_key, summary.model_dump(), ANALYTICS_TTL)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
