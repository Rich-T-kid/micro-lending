from typing import Union, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
