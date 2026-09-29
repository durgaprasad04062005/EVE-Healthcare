"""
FastAPI dependencies shared across multiple routers.

The most important one here is `get_current_user`, which extracts
and validates the JWT from the Authorization header, then loads
the corresponding user from the database.

Usage in any protected route:
    async def my_endpoint(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        ...

If the token is missing, expired, or invalid, FastAPI automatically
returns 401 Unauthorized before the route handler even runs.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.user import User

# HTTPBearer extracts the token from the "Authorization: Bearer <token>" header.
# auto_error=False lets us return a custom 401 message instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validates the JWT and returns the authenticated user.

    Raises HTTP 401 if:
    - No Authorization header is present
    - The token is expired or invalid
    - The user ID in the token doesn't exist in the database
    - The user account is inactive
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
