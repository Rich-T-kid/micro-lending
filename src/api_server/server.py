from typing import Union, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import models
import uuid
import datetime
import jwt
import hashlib
from sqlalchemy.exc import IntegrityError

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


Secret_key = "your_secret"
security = HTTPBearer()
db = models.Database()

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
#TODO: Good place for a cron job / stored procedure to periodically assess risk on pending applications
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
    """Accept loan offer (Borrower) - Dummy implementation"""
    session = db.get_session()
    try:
        # TODO: Implement actual loan offer acceptance logic
        # For now, return a dummy response
        return models.LoanResponse(
            loan_id=12345,
            borrower_id=1,
            lender_id=2,
            principal_amount=5000.00,
            interest_rate=12.5,
            term_months=24,
            status="active",
            balance_remaining=5000.00,
            created_at="2025-10-21T12:00:00Z"
        )
    except Exception as e:
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
        
        return models.LoanResponse(
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
        
        # TODO: this doesnt work right now, moving on
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
        # Get all loans where user is lender
        loans = session.query(models.Loan).filter(models.Loan.lender_id == user_id).all()
        
        total_invested = sum(loan.principal_amount for loan in loans)
        active_loans = len([loan for loan in loans if loan.status == 'active'])
        
        # Calculate total earned (simplified - sum of all interest payments)
        total_earned = 0
        for loan in loans:
            payments = session.query(models.Repayment).filter(models.Repayment.loan_id == loan.loan_id).all()
            total_earned += sum(payment.interest_portion for payment in payments)
        
        # Calculate default rate
        defaulted_loans = len([loan for loan in loans if loan.status == 'defaulted'])
        default_rate = defaulted_loans / len(loans) if loans else 0
        
        # Calculate average return (simplified)
        average_return = (total_earned / total_invested * 100) if total_invested > 0 else 0
        
        # Calculate pending payments
        pending_payments = sum(loan.balance_remaining for loan in loans if loan.status == 'active')
        
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
        
        # Since AutoLendingConfig table doesn't exist yet, return default configuration
        # This is a placeholder implementation until the auto-lending feature is fully developed
        return models.AutoLendingConfigResponse(
            config_id=1,  # Placeholder config ID
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
        
        # Since AutoLendingConfig table doesn't exist yet, return updated configuration
        # This is a placeholder implementation until the auto-lending feature is fully developed
        return models.AutoLendingConfigResponse(
            config_id=1,  # Placeholder config ID
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
            reviewee_id=reviewee_id,  # Return the generated ID
            rating=new_rating.rating,
            comment=new_rating.comment,
            date_created=new_rating.created_at,
            successful=True
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
async def get_admin_dashboard():
    """Get admin dashboard data"""
    session = db.get_session()
    try:
        # Get total users
        total_users = session.query(models.UserAccount).count()
        
        # Get active loans
        active_loans = session.query(models.Loan).filter(models.Loan.status == 'active').count()
        
        # Get pending applications
        pending_applications = session.query(models.LoanApplication).filter(
            models.LoanApplication.status == 'pending'
        ).count()
        
        # Get total loan volume
        loans = session.query(models.Loan).all()
        total_loan_volume = sum(loan.principal_amount for loan in loans)
        
        # Calculate revenue this month (simplified - sum of interest payments)
        from datetime import datetime, timedelta
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        monthly_payments = session.query(models.Repayment).filter(
            models.Repayment.created_at >= current_month_start
        ).all()
        revenue_this_month = sum(payment.amount * 0.05 for payment in monthly_payments)  # 5% estimated interest
        
        # Calculate default rate
        total_loans = len(loans)
        defaulted_loans = len([loan for loan in loans if loan.status == 'defaulted'])
        default_rate = defaulted_loans / total_loans if total_loans > 0 else 0
        
        # Get compliance issues (simplified - dummy count since FraudAlert model doesn't exist)
        compliance_issues = 3  # Dummy value
        
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

@app.get("/admin/loans/approval")
async def get_loans_pending_approval(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get loans pending manual review"""
    session = db.get_session()
    try:
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
            actor_id=1,  #TODO: (replace with jwt logic later) This should be from JWT token in real implementation
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
    # Return dummy data since FraudAlert model doesn't exist yet
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
        
        # Get loans originated in period
        loans_in_period = session.query(models.Loan).filter(
            models.Loan.start_date >= date_from,
            models.Loan.start_date <= date_to
        ).all()
        
        total_loans_originated = len(loans_in_period)
        total_loan_volume = sum(loan.principal_amount for loan in loans_in_period)
        average_loan_size = total_loan_volume / total_loans_originated if total_loans_originated > 0 else 0
        
        # Calculate default rate
        all_loans = session.query(models.Loan).all()
        defaulted_loans = len([loan for loan in all_loans if loan.status == 'defaulted'])
        default_rate = defaulted_loans / len(all_loans) if all_loans else 0
        
        # Calculate revenue
        payments_in_period = session.query(models.Repayment).filter(
            models.Repayment.created_at >= date_from,
            models.Repayment.created_at <= date_to
        ).all()
        revenue_generated = sum(payment.amount * 0.05 for payment in payments_in_period)  # 5% estimated interest
        
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
        
        payments = session.query(models.Repayment).filter(
            models.Repayment.created_at >= start_date,
            models.Repayment.created_at <= end_date
        ).all()
        
        # Calculate totals
        total_revenue = sum(payment.amount * 0.05 for payment in payments)  # 5% estimated interest
        fee_revenue = total_revenue * 0.6  # Simplified: 60% from fees
        interest_revenue = total_revenue * 0.4  # Simplified: 40% from interest
        
        # Create breakdown data (simplified monthly breakdown)
        breakdown_data = []
        if breakdown_by == "month":
            for i in range(12):
                month_start = start_date + timedelta(days=30*i)
                month_end = start_date + timedelta(days=30*(i+1))
                month_payments = [p for p in payments if month_start <= p.created_at < month_end]
                month_revenue = sum(p.amount * 0.05 for p in month_payments)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
