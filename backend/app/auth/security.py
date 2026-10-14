"""
Authentication and security utilities.

Note: We use bcrypt directly instead of passlib.CryptContext because passlib 1.7.4
has an internal detect_wrap_bug() that passes a >72-byte string to bcrypt, which
raises ValueError in bcrypt>=4.x. Going direct avoids this incompatibility.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt as _bcrypt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# JWT configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash. Truncates to 72 bytes (bcrypt limit)."""
    try:
        # BCrypt limit is 72 bytes — truncate raw bytes before hashing
        password_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return _bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (cost factor 12). Truncates to 72 bytes."""
    # BCrypt limit is 72 bytes — truncate raw bytes before hashing
    password_bytes = password.encode('utf-8')[:72]
    return _bcrypt.hashpw(password_bytes, _bcrypt.gensalt(rounds=12)).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token (typically {"sub": user_id})
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    # Get secret key from settings, fail if not configured
    if not settings.secret_key:
        raise ValueError(
            "SECRET_KEY not configured. Set SECRET_KEY environment variable."
        )
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        if not settings.secret_key:
            logger.error("SECRET_KEY not configured")
            return None
        
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None
