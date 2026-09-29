"""
Diagnostic Tests router.

Endpoints:
  GET   /tests/            — list all tests
  POST  /tests/            — create a test
  GET   /tests/{test_id}   — get a test by ID
  PATCH /tests/{test_id}   — update a test

Note: Tests are global catalogue entries (name + description, no price).
Price is set when a test is added to a specific centre via
POST /centres/{centre_id}/tests/{test_id}.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.test import TestCreate, TestResponse, TestUpdate
from app.services import catalogue_service

router = APIRouter()


@router.get(
    "/",
    response_model=list[TestResponse],
    summary="List all diagnostic tests",
)
async def list_tests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[TestResponse]:
    """Returns a paginated list of all diagnostic tests in the system."""
    tests = await catalogue_service.list_tests(db, skip=skip, limit=limit)
    return [TestResponse.model_validate(t) for t in tests]


@router.post(
    "/",
    response_model=TestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new diagnostic test",
    responses={409: {"description": "Test name already exists"}},
)
async def create_test(
    data: TestCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> TestResponse:
    """
    Create a new diagnostic test entry.
    Test names must be unique.
    Price is NOT set here — it is set per-centre when adding the test to a centre.
    """
    try:
        test = await catalogue_service.create_test(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TestResponse.model_validate(test)


@router.get(
    "/{test_id}",
    response_model=TestResponse,
    summary="Get a diagnostic test by ID",
    responses={404: {"description": "Test not found"}},
)
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> TestResponse:
    """Returns a single diagnostic test by its ID."""
    test = await catalogue_service.get_test(db, test_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic test '{test_id}' not found",
        )
    return TestResponse.model_validate(test)


@router.patch(
    "/{test_id}",
    response_model=TestResponse,
    summary="Update a diagnostic test",
    responses={
        404: {"description": "Test not found"},
        409: {"description": "Test name already exists"},
    },
)
async def update_test(
    test_id: str,
    data: TestUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> TestResponse:
    """Partially update a diagnostic test. Requires authentication."""
    test = await catalogue_service.get_test(db, test_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic test '{test_id}' not found",
        )
    try:
        updated = await catalogue_service.update_test(db, test, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TestResponse.model_validate(updated)
