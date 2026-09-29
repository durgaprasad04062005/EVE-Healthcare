"""
Database engine and session setup.

We use SQLAlchemy 2.x with async support (asyncpg driver for PostgreSQL).
Every request gets its own session via the `get_db` FastAPI dependency.

Why async?
FastAPI is built on top of asyncio (via Starlette). Using an async
database driver means the event loop is not blocked while waiting for
database I/O — the server can handle other requests in that time.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# The engine manages the connection pool.
# echo=False in production — set to True temporarily if you need to debug SQL.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,  # verify connections are alive before using them
)

# Session factory — we call this to get new sessions.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep attribute values accessible after commit
)


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy models.
    All models inherit from this class so Alembic can discover them.
    """
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.

    Usage in a route:
        async def my_endpoint(db: AsyncSession = Depends(get_db)): ...

    The session is always closed after the request completes, whether
    the request succeeded or raised an exception.
    """
    async with AsyncSessionLocal() as session:
        yield session
