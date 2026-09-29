"""
Tests for Diagnostic Centres and Tests APIs.

Covers:
- List centres (empty + populated)
- Create centre (auth required)
- Get centre by ID
- Update centre
- Get nonexistent centre
- List tests
- Create test (auth required)
- Duplicate test name
- Get test by ID
- Add test to centre with price
- Duplicate test at centre
- List tests at centre
- Update price at centre
- Remove test from centre
- Add test to nonexistent centre
"""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper to create a centre
# ---------------------------------------------------------------------------

async def create_centre(client: AsyncClient, headers: dict, name: str = "Test Lab") -> dict:
    r = await client.post("/centres/", json={
        "name": name,
        "location": "123 Main Street, Johannesburg",
    }, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def create_test(client: AsyncClient, headers: dict, name: str = "Blood Glucose") -> dict:
    r = await client.post("/tests/", json={"name": name, "description": "Measures blood sugar levels"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Centres
# ---------------------------------------------------------------------------

async def test_list_centres_empty(client: AsyncClient):
    """List centres returns an empty list when no centres exist."""
    r = await client.get("/centres/")
    assert r.status_code == 200
    assert r.json() == []


async def test_create_centre_requires_auth(client: AsyncClient):
    """Creating a centre without a token returns 401."""
    r = await client.post("/centres/", json={
        "name": "Unauthorized Lab",
        "location": "Somewhere",
    })
    assert r.status_code == 401


async def test_create_centre_success(client: AsyncClient, auth_headers: dict):
    """Authenticated user can create a centre."""
    r = await client.post("/centres/", json={
        "name": "City Health Lab",
        "location": "45 Hospital Drive, Cape Town",
        "description": "Full-service diagnostic lab",
    }, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "City Health Lab"
    assert body["location"] == "45 Hospital Drive, Cape Town"
    assert "id" in body


async def test_list_centres_after_create(client: AsyncClient, auth_headers: dict):
    """After creating a centre, it appears in the list."""
    await create_centre(client, auth_headers, "Visible Lab")
    r = await client.get("/centres/")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "Visible Lab" in names


async def test_get_centre_by_id(client: AsyncClient, auth_headers: dict):
    """Can retrieve a centre by its UUID."""
    centre = await create_centre(client, auth_headers, "Lookup Lab")
    r = await client.get(f"/centres/{centre['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == centre["id"]
    assert r.json()["name"] == "Lookup Lab"


async def test_get_centre_not_found(client: AsyncClient):
    """Requesting a nonexistent centre ID returns 404."""
    r = await client.get("/centres/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_update_centre(client: AsyncClient, auth_headers: dict):
    """Can partially update a centre's details."""
    centre = await create_centre(client, auth_headers, "Old Name Lab")
    r = await client.patch(
        f"/centres/{centre['id']}",
        json={"name": "New Name Lab"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New Name Lab"
    assert r.json()["location"] == centre["location"]  # unchanged


async def test_update_centre_not_found(client: AsyncClient, auth_headers: dict):
    """Updating a nonexistent centre returns 404."""
    r = await client.patch(
        "/centres/00000000-0000-0000-0000-000000000000",
        json={"name": "Ghost Lab"},
        headers=auth_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests (diagnostic test catalogue)
# ---------------------------------------------------------------------------

async def test_list_tests_empty(client: AsyncClient):
    r = await client.get("/tests/")
    assert r.status_code == 200
    assert r.json() == []


async def test_create_test_requires_auth(client: AsyncClient):
    r = await client.post("/tests/", json={"name": "HbA1c"})
    assert r.status_code == 401


async def test_create_test_success(client: AsyncClient, auth_headers: dict):
    r = await client.post("/tests/", json={
        "name": "Full Blood Count",
        "description": "Measures red/white blood cells and platelets",
    }, headers=auth_headers)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Full Blood Count"
    assert "id" in body
    # Price is NOT returned here — it's centre-specific
    assert "price" not in body


async def test_create_test_duplicate_name(client: AsyncClient, auth_headers: dict):
    """Creating two tests with the same name returns 409."""
    await client.post("/tests/", json={"name": "Duplicate Test"}, headers=auth_headers)
    r = await client.post("/tests/", json={"name": "Duplicate Test"}, headers=auth_headers)
    assert r.status_code == 409


async def test_get_test_by_id(client: AsyncClient, auth_headers: dict):
    test = await create_test(client, auth_headers, "Thyroid Panel")
    r = await client.get(f"/tests/{test['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Thyroid Panel"


async def test_get_test_not_found(client: AsyncClient):
    r = await client.get("/tests/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Centre → Tests association (price management)
# ---------------------------------------------------------------------------

async def test_add_test_to_centre(client: AsyncClient, auth_headers: dict):
    """Can add a test to a centre with a specific price."""
    centre = await create_centre(client, auth_headers, "Price Lab A")
    test = await create_test(client, auth_headers, "Cholesterol Screen")

    r = await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "250.00"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["test_id"] == test["id"]
    assert float(body["price"]) == 250.00
    assert body["test_name"] == "Cholesterol Screen"


async def test_add_duplicate_test_to_centre(client: AsyncClient, auth_headers: dict):
    """Adding the same test to the same centre twice returns 409."""
    centre = await create_centre(client, auth_headers, "Dup Centre Lab")
    test = await create_test(client, auth_headers, "Urine Analysis")

    await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "100.00"},
        headers=auth_headers,
    )
    r = await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "120.00"},
        headers=auth_headers,
    )
    assert r.status_code == 409


async def test_list_tests_at_centre(client: AsyncClient, auth_headers: dict):
    """GET /centres/{id}/tests returns all tests offered at that centre with prices."""
    centre = await create_centre(client, auth_headers, "Multi Test Centre")
    test1 = await create_test(client, auth_headers, "Liver Function")
    test2 = await create_test(client, auth_headers, "Kidney Function")

    await client.post(f"/centres/{centre['id']}/tests/{test1['id']}", json={"price": "300"}, headers=auth_headers)
    await client.post(f"/centres/{centre['id']}/tests/{test2['id']}", json={"price": "280"}, headers=auth_headers)

    r = await client.get(f"/centres/{centre['id']}/tests")
    assert r.status_code == 200
    names = {t["test_name"] for t in r.json()}
    assert "Liver Function" in names
    assert "Kidney Function" in names


async def test_update_centre_test_price(client: AsyncClient, auth_headers: dict):
    """Can update the price of a test at a centre."""
    centre = await create_centre(client, auth_headers, "Price Update Centre")
    test = await create_test(client, auth_headers, "Vitamin D")

    await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "400"},
        headers=auth_headers,
    )
    r = await client.put(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "450"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert float(r.json()["price"]) == 450.0


async def test_remove_test_from_centre(client: AsyncClient, auth_headers: dict):
    """Can remove a test from a centre. The test itself still exists."""
    centre = await create_centre(client, auth_headers, "Removal Centre")
    test = await create_test(client, auth_headers, "Iron Studies")

    await client.post(
        f"/centres/{centre['id']}/tests/{test['id']}",
        json={"price": "150"},
        headers=auth_headers,
    )
    r = await client.delete(
        f"/centres/{centre['id']}/tests/{test['id']}",
        headers=auth_headers,
    )
    assert r.status_code == 204

    # Test should no longer appear at this centre
    r = await client.get(f"/centres/{centre['id']}/tests")
    assert r.status_code == 200
    assert r.json() == []

    # But the test itself still exists globally
    r = await client.get(f"/tests/{test['id']}")
    assert r.status_code == 200


async def test_add_test_to_nonexistent_centre(client: AsyncClient, auth_headers: dict):
    """Adding a test to a nonexistent centre returns 404."""
    test = await create_test(client, auth_headers, "Hepatitis B Screen")
    r = await client.post(
        "/centres/00000000-0000-0000-0000-000000000000/tests/" + test["id"],
        json={"price": "200"},
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_add_nonexistent_test_to_centre(client: AsyncClient, auth_headers: dict):
    """Adding a nonexistent test to a centre returns 404."""
    centre = await create_centre(client, auth_headers, "Valid Centre")
    r = await client.post(
        f"/centres/{centre['id']}/tests/00000000-0000-0000-0000-000000000000",
        json={"price": "200"},
        headers=auth_headers,
    )
    assert r.status_code == 404
