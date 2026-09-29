"""
Authentication router.

Routes are intentionally thin:
1. Validate input (Pydantic does this automatically).
2. Call the service.
3. Map the result to an HTTP response.

All business logic lives in auth_service.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter()


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
async def signup(
    data: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new user account and return a JWT access token.

    - Email must be unique.
    - Password must be at least 8 characters.
    - Returns a bearer token that can be used for authenticated requests.
    """
    try:
        _user, token = await auth_service.signup(db, data)
    except ValueError as exc:
        # The service raises ValueError for duplicate emails
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TokenResponse(access_token=token)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in and receive a JWT token",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email and password.

    Returns a JWT bearer token on success.
    Returns 401 for invalid email or wrong password (same message — intentional).
    """
    try:
        _user, token = await auth_service.login(db, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
    responses={401: {"description": "Not authenticated"}},
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Returns the profile of the currently authenticated user.
    Useful for verifying a token is still valid.
    """
    return UserResponse.model_validate(current_user)
