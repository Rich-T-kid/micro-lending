# =============================================================================
# IMPORTS
# =============================================================================
from typing import Union, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status, Query, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import models
import uuid
import jwt
import hashlib
from sqlalchemy.exc import IntegrityError

# =============================================================================
# APP CONFIGURATION
# =============================================================================

# Create FastAPI instance with metadata
app = FastAPI(
    title="Micro-Lending API",
    description="A simple micro-lending platform API",
    version="1.0.0"
)

# Global configuration
Secret_key = "your_secret"
security = HTTPBearer()
db = models.Database()

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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

# =============================================================================
# CORE/HEALTH ENDPOINTS
# =============================================================================

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

# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@app.post("/auth/login", response_model=models.TokenResponse)
async def login(login_request: models.LoginRequest):
    """User login endpoint"""
    session = db.get_session()
    try:
        # Authenticate user (simplified)
        user = session.query(models.UserAccount).filter(
            models.UserAccount.email == login_request.email
        ).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # In a real app, verify password hash
        # For now, we'll accept any password
        
        # Generate JWT tokens
        access_payload = {
            "user_id": user.user_id,
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        refresh_payload = {
            "user_id": user.user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        
        access_token = jwt.encode(access_payload, Secret_key, algorithm="HS256")
        refresh_token = jwt.encode(refresh_payload, Secret_key, algorithm="HS256")
        
        return models.TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=refresh_token
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/auth/refresh", response_model=models.TokenResponse)
async def refresh_token(refresh_request: models.RefreshTokenRequest):
    """Refresh access token endpoint"""
    try:
        # Verify refresh token
        payload = jwt.decode(refresh_request.refresh_token, Secret_key, algorithms=["HS256"])
        
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Generate new access token
        access_payload = {
            "user_id": payload["user_id"],
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        access_token = jwt.encode(access_payload, Secret_key, algorithm="HS256")
        
        return models.TokenResponse(
            access_token=access_token,
            token_type="bearer"
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# USER MANAGEMENT ENDPOINTS
# =============================================================================

@app.post("/users", response_model=models.UserResponse, status_code=201)
async def create_user(user_data: models.UserCreateRequest):
    """Create a new user account"""
    session = db.get_session()
    try:
        # Hash password (simplified)
        hashed_password = hash_password(user_data.password)
        
        # Parse birthdate if provided
        birthdate = None
        if user_data.birthdate:
            try:
                birthdate = datetime.strptime(user_data.birthdate, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid birthdate format. Use YYYY-MM-DD")
        
        # Create new user
        new_user = models.UserAccount(
            name_first=user_data.first_name,
            name_last=user_data.last_name,
            email=user_data.email,
            phone=user_data.phone,
            date_of_birth=birthdate
        )
        
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        
        return models.UserResponse(
            user_id=new_user.user_id,
            email=new_user.email,
            first_name=new_user.name_first,
            last_name=new_user.name_last,
            phone=new_user.phone,
            birthdate=new_user.date_of_birth.isoformat() if new_user.date_of_birth else None,
            status=new_user.status,
            created_at=new_user.created_at.isoformat(),
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
                first_name=user.name_first,
                last_name=user.name_last,
                phone=user.phone,
                birthdate=user.date_of_birth.isoformat() if user.date_of_birth else None,
                status=user.status,
                created_at=user.created_at.isoformat(),
                preferred_language=None,  # Not in DB model
                marketing_consent=None   # Not in DB model
            ) for user in users
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/users/{user_id}", response_model=models.UserResponse)
async def get_user(user_id: int):
    """Get a specific user by ID"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return models.UserResponse(
            user_id=user.user_id,
            email=user.email,
            first_name=user.name_first,
            last_name=user.name_last,
            phone=user.phone,
            birthdate=user.date_of_birth.isoformat() if user.date_of_birth else None,
            status=user.status,
            created_at=user.created_at.isoformat(),
            preferred_language=None,  # Not in DB model
            marketing_consent=None   # Not in DB model
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.put("/users/{user_id}", response_model=models.UserResponse)
async def update_user(user_id: int, user_data: models.UserUpdateRequest):
    """Update a user's information"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update fields if provided
        if user_data.first_name is not None:
            user.name_first = user_data.first_name
        if user_data.last_name is not None:
            user.name_last = user_data.last_name
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.phone is not None:
            user.phone = user_data.phone
        if user_data.birthdate is not None:
            try:
                user.date_of_birth = datetime.strptime(user_data.birthdate, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid birthdate format. Use YYYY-MM-DD")
        if user_data.status is not None:
            user.status = user_data.status
        
        session.commit()
        session.refresh(user)
        
        return models.UserResponse(
            user_id=user.user_id,
            email=user.email,
            first_name=user.name_first,
            last_name=user.name_last,
            phone=user.phone,
            birthdate=user.date_of_birth.isoformat() if user.date_of_birth else None,
            status=user.status,
            created_at=user.created_at.isoformat(),
            preferred_language=user_data.preferred_language,
            marketing_consent=user_data.marketing_consent
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """Delete a user account"""
    session = db.get_session()
    try:
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        session.delete(user)
        session.commit()
        
        return  # 204 No Content
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# KYC MANAGEMENT ENDPOINTS  
# =============================================================================

@app.post("/users/{user_id}/kyc", response_model=models.KYCResponse, status_code=201)
async def submit_kyc(user_id: int, kyc_data: models.KYCSubmissionRequest):
    """Submit KYC/identity verification documents"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if KYC already exists
        existing_kyc = session.query(models.IdentityKyc).filter(
            models.IdentityKyc.user_id == user_id
        ).first()
        if existing_kyc:
            raise HTTPException(status_code=400, detail="KYC already submitted for this user")
        
        # Hash the government ID number (simple hashing for demo)
        import hashlib
        id_hash = hashlib.sha256(kyc_data.government_id_number.encode()).digest()
        
        # Create KYC record
        new_kyc = models.IdentityKyc(
            user_id=user_id,
            government_id_type=kyc_data.government_id_type,
            government_id_hash=id_hash,
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
            verified_at=new_kyc.verified_at.isoformat() if new_kyc.verified_at else None
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
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get KYC record
        kyc = session.query(models.IdentityKyc).filter(
            models.IdentityKyc.user_id == user_id
        ).first()
        if not kyc:
            raise HTTPException(status_code=404, detail="No KYC record found for this user")
        
        return models.KYCResponse(
            kyc_id=kyc.kyc_id,
            user_id=kyc.user_id,
            government_id_type=kyc.government_id_type,
            address_line_1=kyc.address_line1,
            address_line_2=kyc.address_line2,
            city=kyc.city,
            state=kyc.state,
            postal_code=kyc.postal_code,
            country=kyc.country,
            status=kyc.status,
            verified_at=kyc.verified_at.isoformat() if kyc.verified_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# =============================================================================
# WALLET/ACCOUNT MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/users/{user_id}/accounts", response_model=List[models.WalletAccountResponse])
async def get_user_accounts(user_id: int):
    """Get all wallet accounts for a user"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get wallet accounts
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
                created_at=account.created_at.isoformat()
            ) for account in accounts
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/users/{user_id}/accounts", response_model=models.WalletAccountResponse, status_code=201)
async def create_wallet_account(user_id: int, account_data: models.CreateWalletRequest):
    """Create a new wallet account for a user"""
    session = db.get_session()
    try:
        # Check if user exists
        user = session.query(models.UserAccount).filter(models.UserAccount.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if currency exists
        currency = session.query(models.Currency).filter(
            models.Currency.currency_code == account_data.currency_code
        ).first()
        if not currency:
            # Create currency if it doesn't exist (simplified)
            new_currency = models.Currency(
                currency_code=account_data.currency_code,
                name=account_data.currency_code,
                decimals=2
            )
            session.add(new_currency)
            session.commit()
        
        # Check if user already has an account in this currency
        existing_account = session.query(models.WalletAccount).filter(
            models.WalletAccount.owner_type == 'USER',
            models.WalletAccount.owner_id == user_id,
            models.WalletAccount.currency_code == account_data.currency_code
        ).first()
        if existing_account:
            raise HTTPException(status_code=400, detail="User already has an account in this currency")
        
        # Create wallet account
        new_account = models.WalletAccount(
            owner_type='USER',
            owner_id=user_id,
            currency_code=account_data.currency_code,
            available_balance=0,
            hold_balance=0,
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
            created_at=new_account.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/accounts/{account_id}/transactions", response_model=models.TransactionHistoryResponse)
async def get_account_transactions(
    account_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    transaction_type: Optional[str] = None
):
    """Get transaction history for a wallet account"""
    session = db.get_session()
    try:
        # Check if account exists
        account = session.query(models.WalletAccount).filter(
            models.WalletAccount.account_id == account_id
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Build query
        query = session.query(models.TransactionLedger).filter(
            models.TransactionLedger.account_id == account_id
        )
        
        # Filter by transaction type if specified
        if transaction_type:
            query = query.filter(models.TransactionLedger.related_type == transaction_type.upper())
        
        # Order by most recent first
        query = query.order_by(models.TransactionLedger.created_at.desc())
        
        # Get total count for pagination
        total_count = query.count()
        total_pages = (total_count + limit - 1) // limit
        
        # Get paginated results
        transactions = query.offset((page - 1) * limit).limit(limit).all()
        
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
                created_at=tx.created_at.isoformat()
            ) for tx in transactions
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
# This is getting too long - let me create this systematically in smaller parts
# =============================================================================
