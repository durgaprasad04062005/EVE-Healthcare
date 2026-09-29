"""
Booking system tests.

Covers:
1. Unauthenticated booking attempt → 401
2. Successful booking creation
3. Amount is server-determined (not client-supplied)
4. Test not offered at centre → 422
5. Appointment in the past → 422
6. List bookings returns only the current user's bookings
7. Get booking by ID
8. Get another user's booking → 403
9. Cancel a PENDING booking
10. Cancel an already-cancelled booking → 400 (invalid state transition)
11. Cancel a booking belonging to another user → 403
12. Invalid booking ID → 404
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixtures: set up a centre and test that are linked (with a price)
# ---------------------------------------------------------------------------

async def setup_centre_and_test(client: AsyncClient, headers: dict) -> tuple[dict, dict]:
    """
    Helper: create a centre and a test, then link them with a price.
    Returns (centre, test) dicts.
    """
    centre_r = await client.post("/centres/", json={
        "name": "Booking Test Lab",
        "location": "1 Test Street",
    }, headers=headers)
    assert centre_r.status_code == 201, centre_r.text
    centre = centre_r.json()

    test_r = await client.post("/tests/", json={
        "name": "Booking Blood Test",
        "description": "Used in booking tests",
    }, headers=headers)
    assert test_r.status_code == 201, test_r.text
    test = test_r.json()

    link_r = await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "350.00"},
        headers=headers,
    )
    assert link_r.status_code == 201, link_r.text

    return centre, test


def future_datetime(hours: int = 48) -> str:
    """Return an ISO 8601 datetime string in the future."""
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return dt.isoformat()


def past_datetime(hours: int = 1) -> str:
    """Return an ISO 8601 datetime string in the past."""
    dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Booking creation
# ---------------------------------------------------------------------------

async def test_create_booking_unauthenticated(client: AsyncClient, auth_headers: dict):
    """Creating a booking without a token returns 401."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    })
    assert r.status_code == 401


async def test_create_booking_success(client: AsyncClient, auth_headers: dict):
    """An authenticated user can create a booking."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["test_id"] == test["id"]
    assert body["centre_id"] == centre["id"]
    assert "id" in body


async def test_booking_amount_is_server_determined(client: AsyncClient, auth_headers: dict):
    """
    The booking amount must come from CentreTest.price, not from the client.
    We set the price to 350.00 when linking, and verify the booking reflects that.
    """
    centre, test = await setup_centre_and_test(client, auth_headers)
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    assert r.status_code == 201
    # Amount must be exactly 350.00 (from CentreTest), regardless of what the client sent
    assert float(r.json()["amount"]) == 350.00


async def test_create_booking_test_not_at_centre(client: AsyncClient, auth_headers: dict):
    """Booking a test that is NOT offered at the chosen centre returns 422."""
    # Create a centre with no tests linked
    centre_r = await client.post("/centres/", json={
        "name": "Empty Centre",
        "location": "No tests here",
    }, headers=auth_headers)
    centre = centre_r.json()

    # Create a test (not linked to the centre above)
    test_r = await client.post("/tests/", json={
        "name": "Unlinked Test",
    }, headers=auth_headers)
    test = test_r.json()

    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    assert r.status_code == 422
    assert "not offered" in r.json()["detail"].lower()


async def test_create_booking_past_appointment(client: AsyncClient, auth_headers: dict):
    """Booking with an appointment datetime in the past returns 422."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": past_datetime(),
    }, headers=auth_headers)
    assert r.status_code == 422


async def test_create_booking_nonexistent_centre(client: AsyncClient, auth_headers: dict):
    """Booking with a nonexistent centre ID returns 422."""
    _centre, test = await setup_centre_and_test(client, auth_headers)
    r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": "00000000-0000-0000-0000-000000000000",
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Listing and retrieval
# ---------------------------------------------------------------------------

async def test_list_bookings_returns_only_own(client: AsyncClient, auth_headers: dict):
    """GET /bookings/ only returns the current user's bookings."""
    centre, test = await setup_centre_and_test(client, auth_headers)

    # Create two bookings as the main user
    for _ in range(2):
        await client.post("/bookings/", json={
            "test_id": test["id"],
            "centre_id": centre["id"],
            "appointment_datetime": future_datetime(),
        }, headers=auth_headers)

    r = await client.get("/bookings/", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    # All bookings belong to the authenticated user
    token_user_id = r.json()[0]["user_id"]
    assert all(b["user_id"] == token_user_id for b in r.json())


async def test_get_booking_by_id(client: AsyncClient, auth_headers: dict):
    """Can retrieve a specific booking by its ID."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    create_r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    booking_id = create_r.json()["id"]

    r = await client.get(f"/bookings/{booking_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == booking_id


async def test_get_booking_not_found(client: AsyncClient, auth_headers: dict):
    """Requesting a nonexistent booking ID returns 404."""
    r = await client.get("/bookings/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert r.status_code == 404


async def test_get_another_users_booking(client: AsyncClient, auth_headers: dict):
    """
    A user cannot access another user's booking.
    Should return 403, not 404.
    """
    # Create a booking as user A (auth_headers)
    centre, test = await setup_centre_and_test(client, auth_headers)
    create_r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    booking_id = create_r.json()["id"]

    # Register user B and try to access user A's booking
    signup_r = await client.post("/auth/signup", json={
        "email": "user_b@example.com",
        "password": "password123",
        "full_name": "User B",
    })
    user_b_token = signup_r.json()["access_token"]
    user_b_headers = {"Authorization": f"Bearer {user_b_token}"}

    r = await client.get(f"/bookings/{booking_id}", headers=user_b_headers)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

async def test_cancel_pending_booking(client: AsyncClient, auth_headers: dict):
    """A PENDING booking can be cancelled."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    create_r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    booking_id = create_r.json()["id"]
    assert create_r.json()["status"] == "PENDING"

    r = await client.post(f"/bookings/{booking_id}/cancel", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"


async def test_cancel_already_cancelled_booking(client: AsyncClient, auth_headers: dict):
    """Cancelling an already-cancelled booking returns 400 (invalid state transition)."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    create_r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    booking_id = create_r.json()["id"]

    # First cancellation — should succeed
    await client.post(f"/bookings/{booking_id}/cancel", headers=auth_headers)

    # Second cancellation — should fail
    r = await client.post(f"/bookings/{booking_id}/cancel", headers=auth_headers)
    assert r.status_code == 400
    assert "cannot cancel" in r.json()["detail"].lower()


async def test_cancel_another_users_booking(client: AsyncClient, auth_headers: dict):
    """A user cannot cancel another user's booking. Returns 403."""
    centre, test = await setup_centre_and_test(client, auth_headers)
    create_r = await client.post("/bookings/", json={
        "test_id": test["id"],
        "centre_id": centre["id"],
        "appointment_datetime": future_datetime(),
    }, headers=auth_headers)
    booking_id = create_r.json()["id"]

    # Register a different user
    signup_r = await client.post("/auth/signup", json={
        "email": "attacker@example.com",
        "password": "password123",
        "full_name": "Attacker",
    })
    attacker_token = signup_r.json()["access_token"]
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    r = await client.post(f"/bookings/{booking_id}/cancel", headers=attacker_headers)
    assert r.status_code == 403
    # Verify the original booking is still PENDING (attacker didn't change it)
    original = await client.get(f"/bookings/{booking_id}", headers=auth_headers)
    assert original.json()["status"] == "PENDING"
