"""
Authentication API endpoints
POST /register, /login, /refresh, /logout
"""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from bson import ObjectId

from app.schemas import UserRegister, UserLogin, TokenResponse, RefreshTokenRequest, UserProfile
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user
)
from app.database import get_db
from app.config import settings

router = APIRouter()


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db=Depends(get_db)):
    """
    Register a new user account.
    
    - Validates email uniqueness
    - Hashes password with bcrypt
    - Assigns default role (developer)
    """
    # Check if email already exists
    if await db.users.find_one({"email": user_data.email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )
    
    # Check if username already exists  
    if await db.users.find_one({"username": user_data.username}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken"
        )
    
    # Create user document
    now = datetime.now(timezone.utc)
    user_doc = {
        "email": user_data.email,
        "username": user_data.username,
        "password_hash": hash_password(user_data.password),
        "full_name": user_data.full_name,
        "role": user_data.role.value,
        "is_active": True,
        "bio": None,
        "skills": [],
        "github_username": None,
        "avatar_url": f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_data.username}",
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    
    # Log activity
    await db.activity_logs.insert_one({
        "user_id": user_doc["id"],
        "action": "user_registered",
        "details": {"email": user_data.email},
        "timestamp": now
    })
    
    return UserProfile(**user_doc)


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db=Depends(get_db)):
    """
    Authenticate user and return JWT tokens.
    
    Returns:
        - access_token (30 min expiry)
        - refresh_token (7 days expiry)
    """
    user = await db.users.find_one({"email": credentials.email})
    
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Contact admin."
        )
    
    user_id = str(user["_id"])
    token_payload = {
        "sub": user_id,
        "email": user["email"],
        "role": user["role"],
        "username": user["username"]
    }
    
    # Update last login
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )
    
    return TokenResponse(
        access_token=create_access_token(token_payload),
        refresh_token=create_refresh_token(token_payload),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db=Depends(get_db)):
    """
    Issue new access token using a valid refresh token.
    Implements sliding window refresh for better UX.
    """
    payload = decode_token(request.refresh_token)
    
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    token_payload = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "role": user["role"],
        "username": user["username"]
    }
    
    return TokenResponse(
        access_token=create_access_token(token_payload),
        refresh_token=create_refresh_token(token_payload),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user's profile"""
    current_user["id"] = str(current_user["_id"])
    return UserProfile(**current_user)
