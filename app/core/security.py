"""
Security utilities: password hashing and JWT handling.

We use `bcrypt` directly (rather than passlib) because passlib is
unmaintained and has compatibility issues with bcrypt >= 4.x.
bcrypt is simpler and well-maintained.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain_password: str) -> str:
    """
    Return a bcrypt hash of the given plaintext password.
    bcrypt.hashpw requires bytes, so we encode the string first.
    The salt is generated automatically by bcrypt.gensalt().
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Store as a string in the database (bcrypt hashes are valid ASCII)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plaintext password matches the stored hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(subject: str) -> str:
    """
    Create a signed JWT access token.

    :param subject: Stored in the 'sub' claim — we use the user's UUID as a string.
    :returns: Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """
    Decode and validate a JWT token.

    :param token: Raw JWT string from the Authorization header.
    :returns: The 'sub' claim (user UUID string).
    :raises ValueError: If the token is expired, invalid, or missing 'sub'.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        subject: str | None = payload.get("sub")
        if subject is None:
            raise ValueError("Token is missing the 'sub' claim")
        return subject
    except JWTError as exc:
        raise ValueError(f"Invalid or expired token: {exc}") from exc
