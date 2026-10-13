"""
Authentication API routes.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, Token, UserResponse, AuthResponse
from app.auth.security import verify_password, get_password_hash, create_access_token
from app.auth.dependencies import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Note: In production, you may want to restrict registration or require
    admin approval. This endpoint is provided for development convenience.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_admin=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create access token
    access_token = create_access_token(data={"sub": new_user.id})
    
    logger.info(f"New user registered: {new_user.email}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": new_user
    }


@router.post("/auth/login", response_model=AuthResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return access token with user info.
    
    Returns:
        JWT access token valid for 24 hours and user information
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    
    # Generic error message to avoid revealing whether email exists
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not user:
        # Still verify a dummy password to prevent timing attacks
        get_password_hash("dummy_password_to_prevent_timing_attack")
        raise auth_error
    
    if not verify_password(credentials.password, user.hashed_password):
        raise auth_error
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id})
    
    logger.info(f"User logged in: {user.email}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user information.
    """
    return current_user
