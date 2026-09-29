"""
Authentication service.

Contains all business logic for user signup and login.
Routes call these functions — they don't contain logic themselves.

Why keep this separate from routes?
- Testable without HTTP: you can unit-test signup/login by calling
  these functions directly with a database session.
- Single responsibility: the route handles HTTP concerns (headers,
  status codes); the service handles domain logic (duplicate check,
  password verification).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import SignupRequest

logger = get_logger(__name__)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Look up a user by email address.
    Returns None if no user with that email exists.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def signup(db: AsyncSession, data: SignupRequest) -> tuple[User, str]:
    """
    Create a new user account.

    :returns: (user, access_token) tuple on success.
    :raises ValueError: if the email is already registered.
    """
    # Check for duplicate email before attempting an INSERT.
    # The database also has a UNIQUE constraint on email, but checking
    # first gives us a cleaner error message.
    existing = await get_user_by_email(db, data.email)
    if existing is not None:
        raise ValueError(f"Email '{data.email}' is already registered")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=user.id)
    logger.info("New user registered: id=%s email=%s", user.id, user.email)
    return user, token


async def login(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    """
    Authenticate a user with email and password.

    :returns: (user, access_token) tuple on success.
    :raises ValueError: if credentials are invalid (intentionally vague).

    Security note: we use the same error message for "email not found"
    and "wrong password" so attackers can't enumerate valid email addresses.
    """
    user = await get_user_by_email(db, email)

    # Deliberately vague: same message for unknown email or wrong password
    invalid_msg = "Invalid email or password"

    if user is None:
        logger.warning("Login attempt with unknown email: %s", email)
        raise ValueError(invalid_msg)

    if not user.is_active:
        raise ValueError(invalid_msg)

    if not verify_password(password, user.hashed_password):
        logger.warning("Failed login attempt for user: id=%s", user.id)
        raise ValueError(invalid_msg)

    token = create_access_token(subject=user.id)
    logger.info("User logged in: id=%s", user.id)
    return user, token
