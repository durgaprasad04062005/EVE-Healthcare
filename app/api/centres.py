"""
Diagnostic Centres router.

Endpoints:
  GET    /centres/                         — list all centres (paginated)
  POST   /centres/                         — create a centre
  GET    /centres/{centre_id}              — get a centre by ID
  PATCH  /centres/{centre_id}              — update a centre
  GET    /centres/{centre_id}/tests        — list tests offered at a centre (with prices)
  POST   /centres/{centre_id}/tests/{test_id}   — add a test to a centre
  PUT    /centres/{centre_id}/tests/{test_id}   — update the price of a test at a centre
  DELETE /centres/{centre_id}/tests/{test_id}   — remove a test from a centre

Read endpoints are public. Write endpoints require authentication.
(Assumption: in a real system, writes would be admin-only. Since the
assignment doesn't define an admin role, we require any valid JWT.)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.centre import (
    CentreCreate,
    CentreResponse,
    CentreTestAdd,
    CentreTestResponse,
    CentreTestUpdate,
    CentreUpdate,
)
from app.services import catalogue_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Centre CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[CentreResponse],
    summary="List all diagnostic centres",
)
async def list_centres(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
) -> list[CentreResponse]:
    """Returns a paginated list of all diagnostic centres."""
    centres = await catalogue_service.list_centres(db, skip=skip, limit=limit)
    return [CentreResponse.model_validate(c) for c in centres]


@router.post(
    "/",
    response_model=CentreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic centre",
)
async def create_centre(
    data: CentreCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),  # auth required
) -> CentreResponse:
    """Creates a new diagnostic centre. Requires authentication."""
    centre = await catalogue_service.create_centre(db, data)
    return CentreResponse.model_validate(centre)


@router.get(
    "/{centre_id}",
    response_model=CentreResponse,
    summary="Get a diagnostic centre by ID",
    responses={404: {"description": "Centre not found"}},
)
async def get_centre(
    centre_id: str,
    db: AsyncSession = Depends(get_db),
) -> CentreResponse:
    """Returns a single diagnostic centre by its ID."""
    centre = await catalogue_service.get_centre(db, centre_id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre '{centre_id}' not found",
        )
    return CentreResponse.model_validate(centre)


@router.patch(
    "/{centre_id}",
    response_model=CentreResponse,
    summary="Update a diagnostic centre",
    responses={404: {"description": "Centre not found"}},
)
async def update_centre(
    centre_id: str,
    data: CentreUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> CentreResponse:
    """Partially update a centre's details. Requires authentication."""
    centre = await catalogue_service.get_centre(db, centre_id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre '{centre_id}' not found",
        )
    updated = await catalogue_service.update_centre(db, centre, data)
    return CentreResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Centre → Tests (what tests are available at a given centre, with prices)
# ---------------------------------------------------------------------------

@router.get(
    "/{centre_id}/tests",
    response_model=list[CentreTestResponse],
    summary="List all tests offered at a centre (with prices)",
    responses={404: {"description": "Centre not found"}},
)
async def list_centre_tests(
    centre_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CentreTestResponse]:
    """
    Returns all diagnostic tests offered at this centre, including the
    centre-specific price for each test.
    """
    centre = await catalogue_service.get_centre(db, centre_id)
    if centre is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic centre '{centre_id}' not found",
        )
    centre_tests = await catalogue_service.list_centre_tests(db, centre_id)
    return [
        CentreTestResponse(
            centre_test_id=ct.id,
            test_id=ct.test_id,
            test_name=ct.test.name,
            test_description=ct.test.description,
            price=ct.price,
        )
        for ct in centre_tests
    ]


@router.post(
    "/{centre_id}/tests/{test_id}",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a test to a centre with a price",
    responses={
        404: {"description": "Centre or test not found"},
        409: {"description": "Test already offered at this centre"},
    },
)
async def add_test_to_centre(
    centre_id: str,
    test_id: str,
    data: CentreTestAdd,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> CentreTestResponse:
    """
    Add a diagnostic test to this centre with a specific price.
    The price is this centre's charge for the test — it can differ from
    what other centres charge for the same test.
    """
    try:
        ct = await catalogue_service.add_test_to_centre(db, centre_id, test_id, data)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc

    return CentreTestResponse(
        centre_test_id=ct.id,
        test_id=ct.test_id,
        test_name=ct.test.name,
        test_description=ct.test.description,
        price=ct.price,
    )


@router.put(
    "/{centre_id}/tests/{test_id}",
    response_model=CentreTestResponse,
    summary="Update the price of a test at a centre",
    responses={404: {"description": "Centre-test association not found"}},
)
async def update_centre_test(
    centre_id: str,
    test_id: str,
    data: CentreTestUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> CentreTestResponse:
    """Update the price of a test that is already offered at this centre."""
    ct = await catalogue_service.get_centre_test(db, centre_id, test_id)
    if ct is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test '{test_id}' is not offered at centre '{centre_id}'",
        )
    updated = await catalogue_service.update_centre_test_price(db, ct, data.price)
    return CentreTestResponse(
        centre_test_id=updated.id,
        test_id=updated.test_id,
        test_name=updated.test.name,
        test_description=updated.test.description,
        price=updated.price,
    )


@router.delete(
    "/{centre_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a test from a centre",
    responses={404: {"description": "Centre-test association not found"}},
)
async def remove_test_from_centre(
    centre_id: str,
    test_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> None:
    """Remove a diagnostic test from this centre. Does not delete the test itself."""
    ct = await catalogue_service.get_centre_test(db, centre_id, test_id)
    if ct is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test '{test_id}' is not offered at centre '{centre_id}'",
        )
    await catalogue_service.remove_test_from_centre(db, ct)
