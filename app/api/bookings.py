"""
Bookings router.

All endpoints require authentication.

Endpoints:
  POST  /bookings/                  — create a booking
  GET   /bookings/                  — list the current user's bookings
  GET   /bookings/{booking_id}      — get a specific booking
  POST  /bookings/{booking_id}/cancel — cancel a pending booking

Authorization:
  Users can only see and modify their OWN bookings.
  Accessing another user's booking returns 403 Forbidden.
  (We use 403 rather than 404 to be honest that the resource exists but
  is not accessible — 404 would leak whether the booking ID exists.)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponse
from app.services import booking_service

router = APIRouter()


def _check_ownership(booking, current_user: User) -> None:
    """
    Raise 403 if the booking doesn't belong to current_user.
    Extracted as a helper so the ownership check is consistent everywhere.
    """
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this booking.",
        )


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a diagnostic test",
    responses={
        401: {"description": "Not authenticated"},
        422: {"description": "Test not offered at this centre, or validation error"},
    },
)
async def create_booking(
    data: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    """
    Create a new booking for a diagnostic test at a specific centre.

    - The appointment datetime must be in the future.
    - The test must be offered at the chosen centre.
    - The booking amount is determined server-side from the centre's price — not from the request body.
    - The booking starts in PENDING status until payment is processed.
    """
    try:
        booking = await booking_service.create_booking(db, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return BookingResponse.model_validate(booking)


@router.get(
    "/",
    response_model=list[BookingResponse],
    summary="List the current user's bookings",
)
async def list_bookings(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingResponse]:
    """
    Returns all bookings belonging to the authenticated user.
    Most recent bookings appear first.
    """
    bookings = await booking_service.get_bookings_for_user(
        db, current_user.id, skip=skip, limit=limit
    )
    return [BookingResponse.model_validate(b) for b in bookings]


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get a specific booking",
    responses={
        403: {"description": "Booking belongs to a different user"},
        404: {"description": "Booking not found"},
    },
)
async def get_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    """
    Returns a single booking by ID.
    Returns 403 if the booking belongs to a different user.
    """
    booking = await booking_service.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{booking_id}' not found",
        )
    _check_ownership(booking, current_user)
    return BookingResponse.model_validate(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a pending booking",
    responses={
        400: {"description": "Booking is not in a cancellable state"},
        403: {"description": "Booking belongs to a different user"},
        404: {"description": "Booking not found"},
    },
)
async def cancel_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingResponse:
    """
    Cancel a booking.

    Only PENDING bookings can be cancelled.
    CONFIRMED, FAILED, and CANCELLED bookings cannot be changed.
    """
    booking = await booking_service.get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{booking_id}' not found",
        )
    _check_ownership(booking, current_user)

    try:
        cancelled = await booking_service.cancel_booking(db, booking)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return BookingResponse.model_validate(cancelled)
