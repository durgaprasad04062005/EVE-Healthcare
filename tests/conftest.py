"""
pytest configuration and shared fixtures.

Test database strategy:
- SQLite in-memory database, shared engine across the test session.
- Schema created once via create_all() at session start.
- Each test wraps all DB operations in a SAVEPOINT, then rolls back
  after the test completes — so every test starts with a clean slate
  without recreating the schema.

Why SAVEPOINT instead of truncating tables?
- Much faster — no DDL operations per test.
- Fully isolated — each test's writes are invisible to other tests.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create the in-memory database and schema once for the whole session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        # connect_args needed for SQLite to share the same in-memory DB
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an isolated database session per test.

    We open a connection, begin a transaction, and then create a session
    bound to that connection. After the test, we roll back the transaction —
    discarding every write the test made without touching the schema.
    """
    async with test_engine.connect() as conn:
        await conn.begin()

        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            yield session

        await conn.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTPX async client with the FastAPI app.
    The get_db dependency is overridden to use the test session,
    so all API calls go through the same rolled-back transaction.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient) -> str:
    """Register a test user and return their JWT token."""
    response = await client.post("/auth/signup", json={
        "email": "testuser@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
    })
    assert response.status_code == 201, f"Auth fixture signup failed: {response.text}"
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def auth_headers(auth_token: str) -> dict:
    """Authorization headers ready for httpx requests."""
    return {"Authorization": f"Bearer {auth_token}"}
