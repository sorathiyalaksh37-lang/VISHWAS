import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


def _check_email(v: str) -> str:
    # Use a permissive regex that accepts local/reserved domains (e.g. .local, .internal)
    if not isinstance(v, str) or not re.match(r"^[^@\s]+@[^@\s]+$", v):
        raise ValueError("Invalid email address format")
    return v


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: str = Field(..., max_length=255, description="User email address")
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _check_email(v)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: str = Field(..., max_length=255, description="User email address")
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _check_email(v)


class Token(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: Optional[str] = None


class UserResponse(BaseModel):
    """Schema for user information response."""
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Schema for authentication response (login/register)."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

