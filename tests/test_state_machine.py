"""
State machine unit tests.

These test the booking state transition rules directly — not via HTTP.
Keeping them as pure unit tests means they run instantly and are
easy to reason about without HTTP noise.

Also tests security invariants (hashed_password never in responses).
"""

import pytest
from httpx import AsyncClient

from app.models.booking import BookingStatus, is_valid_booking_transition


# ---------------------------------------------------------------------------
# State machine unit tests (no HTTP, no database)
# ---------------------------------------------------------------------------

def test_pending_can_transition_to_confirmed():
    assert is_valid_booking_transition(BookingStatus.PENDING, BookingStatus.CONFIRMED)


def test_pending_can_transition_to_failed():
    assert is_valid_booking_transition(BookingStatus.PENDING, BookingStatus.FAILED)


def test_pending_can_transition_to_cancelled():
    assert is_valid_booking_transition(BookingStatus.PENDING, BookingStatus.CANCELLED)


def test_confirmed_cannot_go_to_pending():
    assert not is_valid_booking_transition(BookingStatus.CONFIRMED, BookingStatus.PENDING)


def test_confirmed_cannot_go_to_failed():
    assert not is_valid_booking_transition(BookingStatus.CONFIRMED, BookingStatus.FAILED)


def test_confirmed_cannot_go_to_cancelled():
    assert not is_valid_booking_transition(BookingStatus.CONFIRMED, BookingStatus.CANCELLED)


def test_failed_cannot_transition_to_anything():
    for target in BookingStatus:
        assert not is_valid_booking_transition(BookingStatus.FAILED, target), (
            f"FAILED should not be able to transition to {target.value}"
        )


def test_cancelled_cannot_transition_to_anything():
    for target in BookingStatus:
        assert not is_valid_booking_transition(BookingStatus.CANCELLED, target), (
            f"CANCELLED should not be able to transition to {target.value}"
        )


def test_pending_cannot_stay_pending():
    """PENDING → PENDING is not a valid transition (no self-loops)."""
    assert not is_valid_booking_transition(BookingStatus.PENDING, BookingStatus.PENDING)


# ---------------------------------------------------------------------------
# Security invariants
# ---------------------------------------------------------------------------

async def test_hashed_password_never_in_signup_response(client: AsyncClient):
    """Signup response must never contain hashed_password."""
    r = await client.post("/auth/signup", json={
        "email": "sectest@example.com",
        "password": "mysecretpassword",
        "full_name": "Security Test",
    })
    assert r.status_code == 201
    response_text = r.text.lower()
    assert "hashed_password" not in response_text
    assert "password" not in r.json()  # token response has no password field


async def test_hashed_password_never_in_me_response(client: AsyncClient):
    """GET /auth/me must never expose hashed_password."""
    signup_r = await client.post("/auth/signup", json={
        "email": "sectest2@example.com",
        "password": "anothersecret",
        "full_name": "Security Test 2",
    })
    token = signup_r.json()["access_token"]

    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "hashed_password" not in body
    assert "password" not in body


async def test_booking_ignores_client_amount(client: AsyncClient, auth_headers: dict):
    """
    Even if the client sends an 'amount' field in the booking request body,
    the server should use the price from CentreTest, not the client value.

    FastAPI/Pydantic silently ignores extra fields not in BookingCreate,
    so 'amount' is stripped before reaching the service.
    """
    # Create centre, test, link at price 350
    centre_r = await client.post("/centres/", json={
        "name": "Amount Test Lab",
        "location": "1 Amount St",
    }, headers=auth_headers)
    centre = centre_r.json()

    test_r = await client.post("/tests/", json={"name": "Amount Test Check"}, headers=auth_headers)
    test = test_r.json()

    await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "350.00"},
        headers=auth_headers,
    )

    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()

    # Include a rogue 'amount' field — should be ignored
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future,
        "amount": "1.00",  # attacker tries to pay R1 for a R350 test
    }, headers=auth_headers)

    assert r.status_code == 201
    # Amount must be 350.00, not 1.00
    assert float(r.json()["amount"]) == 350.00, (
        f"Server should use CentreTest price (350.00), not client-supplied amount. "
        f"Got: {r.json()['amount']}"
    )
