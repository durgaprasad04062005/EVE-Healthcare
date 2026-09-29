"""
Pydantic schemas for authentication endpoints.

Schemas serve as the contract between the HTTP layer and the service layer:
- They validate and coerce incoming request data.
- They define exactly what fields are returned in responses.
- They keep internal model details (like hashed_password) from leaking out.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class SignupRequest(BaseModel):
    """Request body for POST /auth/signup."""

    email: EmailStr = Field(..., description="User's email address (must be unique)")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: str = Field(..., min_length=1, max_length=255, description="User's full name")

    @field_validator("password")
    @classmethod
    def password_not_whitespace(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("Password must not start or end with whitespace")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name must not be blank")
        return v.strip()


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class TokenResponse(BaseModel):
    """
    Response body for successful login or signup.
    Returns a JWT bearer token.
    """

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """
    Public representation of a user.
    Never includes hashed_password or other internal fields.
    """

    id: str
    email: str
    full_name: str
    is_active: bool

    # Allow constructing this from a SQLAlchemy ORM object
    model_config = {"from_attributes": True}
