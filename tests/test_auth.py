"""
Authentication tests.

Covers:
1. Successful signup
2. Duplicate signup (same email)
3. Signup with invalid data (short password, missing field)
4. Successful login
5. Login with wrong password
6. Login with unknown email
7. Accessing a protected endpoint without a token
8. Accessing a protected endpoint with a valid token (GET /auth/me)
9. Accessing a protected endpoint with an invalid/expired token
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Signup tests
# ---------------------------------------------------------------------------

async def test_signup_success(client: AsyncClient):
    """A new user can sign up and receives a JWT token."""
    response = await client.post("/auth/signup", json={
        "email": "alice@example.com",
        "password": "securepassword1",
        "full_name": "Alice Smith",
    })
    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20  # sanity check it's a real JWT


async def test_signup_duplicate_email(client: AsyncClient):
    """Signing up with an email that already exists returns 409."""
    payload = {
        "email": "bob@example.com",
        "password": "securepassword1",
        "full_name": "Bob Jones",
    }
    # First signup — should succeed
    r1 = await client.post("/auth/signup", json=payload)
    assert r1.status_code == 201

    # Second signup with same email — should fail
    r2 = await client.post("/auth/signup", json=payload)
    assert r2.status_code == 409
    assert "already registered" in r2.json()["detail"].lower()


async def test_signup_password_too_short(client: AsyncClient):
    """Password shorter than 8 characters is rejected at the schema level."""
    response = await client.post("/auth/signup", json={
        "email": "charlie@example.com",
        "password": "short",
        "full_name": "Charlie Brown",
    })
    assert response.status_code == 422  # Pydantic validation error


async def test_signup_invalid_email(client: AsyncClient):
    """Non-email string in the email field is rejected."""
    response = await client.post("/auth/signup", json={
        "email": "not-an-email",
        "password": "securepassword1",
        "full_name": "Test User",
    })
    assert response.status_code == 422


async def test_signup_missing_field(client: AsyncClient):
    """Missing required field (full_name) returns 422."""
    response = await client.post("/auth/signup", json={
        "email": "dave@example.com",
        "password": "securepassword1",
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

async def test_login_success(client: AsyncClient):
    """A registered user can log in and receives a JWT token."""
    # Register first
    await client.post("/auth/signup", json={
        "email": "eve@example.com",
        "password": "mypassword123",
        "full_name": "Eve Baker",
    })
    # Now log in
    response = await client.post("/auth/login", json={
        "email": "eve@example.com",
        "password": "mypassword123",
    })
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient):
    """Wrong password returns 401 with a vague error message."""
    await client.post("/auth/signup", json={
        "email": "frank@example.com",
        "password": "correctpassword",
        "full_name": "Frank White",
    })
    response = await client.post("/auth/login", json={
        "email": "frank@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


async def test_login_unknown_email(client: AsyncClient):
    """Login with an email that doesn't exist returns 401 (same message as wrong password)."""
    response = await client.post("/auth/login", json={
        "email": "nobody@example.com",
        "password": "somepassword",
    })
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Protected endpoint tests
# ---------------------------------------------------------------------------

async def test_get_me_unauthenticated(client: AsyncClient):
    """Accessing /auth/me without a token returns 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_get_me_authenticated(client: AsyncClient):
    """Accessing /auth/me with a valid token returns the user's profile."""
    # Register and get a token
    signup_resp = await client.post("/auth/signup", json={
        "email": "grace@example.com",
        "password": "mypassword123",
        "full_name": "Grace Hopper",
    })
    token = signup_resp.json()["access_token"]

    # Access protected endpoint
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "grace@example.com"
    assert body["full_name"] == "Grace Hopper"
    assert "hashed_password" not in body  # must never be exposed


async def test_get_me_invalid_token(client: AsyncClient):
    """A malformed or tampered JWT returns 401."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code == 401
