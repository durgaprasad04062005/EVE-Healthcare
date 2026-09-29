"""
Booking service.

Responsible for:
1. Creating bookings (with server-side price lookup)
2. Retrieving bookings (with authorization checks)
3. Cancelling bookings (enforcing state machine rules)
4. Updating booking status (called by the payment service)

State machine rules live here, not in the routes.
The routes only handle HTTP translation.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus, is_valid_booking_transition
from app.models.centre_test import CentreTest
from app.schemas.booking import BookingCreate

logger = get_logger(__name__)


async def get_booking_by_id(db: AsyncSession, booking_id: str) -> Booking | None:
    """Return a booking by ID, or None if not found."""
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    return result.scalar_one_or_none()


async def get_bookings_for_user(
    db: AsyncSession, user_id: str, skip: int = 0, limit: int = 50
) -> list[Booking]:
    """Return all bookings belonging to a specific user (paginated)."""
    result = await db.execute(
        select(Booking)
        .where(Booking.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .order_by(Booking.created_at.desc())
    )
    return list(result.scalars().all())


async def create_booking(
    db: AsyncSession, user_id: str, data: BookingCreate
) -> Booking:
    """
    Create a new booking.

    Key validations:
    1. The test must be offered at the chosen centre (CentreTest row must exist).
       If not → ValueError (422 in the route)
    2. The amount is taken from CentreTest.price — never from the client.

    We do NOT check that appointment_datetime is in the future here because
    that validation already happened in the Pydantic schema (BookingCreate).
    """
    # Look up the CentreTest to validate the combination and get the price
    result = await db.execute(
        select(CentreTest).where(
            CentreTest.centre_id == data.centre_id,
            CentreTest.test_id == data.test_id,
        )
    )
    centre_test = result.scalar_one_or_none()

    if centre_test is None:
        raise ValueError(
            f"Test '{data.test_id}' is not offered at centre '{data.centre_id}'. "
            "Please check the centre's available tests."
        )

    booking = Booking(
        user_id=user_id,
        test_id=data.test_id,
        centre_id=data.centre_id,
        appointment_datetime=data.appointment_datetime,
        amount=centre_test.price,  # price from the database — never trusting the client
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    logger.info(
        "Booking created: id=%s user=%s centre=%s test=%s amount=%s",
        booking.id, user_id, data.centre_id, data.test_id, centre_test.price
    )
    return booking


async def cancel_booking(db: AsyncSession, booking: Booking) -> Booking:
    """
    Cancel a booking.

    Only PENDING bookings can be cancelled.
    :raises ValueError: if the booking is not in a cancellable state.
    """
    if not is_valid_booking_transition(booking.status, BookingStatus.CANCELLED):
        raise ValueError(
            f"Cannot cancel a booking with status '{booking.status.value}'. "
            "Only PENDING bookings can be cancelled."
        )

    booking.status = BookingStatus.CANCELLED
    await db.commit()
    await db.refresh(booking)
    logger.info("Booking cancelled: id=%s", booking.id)
    return booking


async def update_booking_status(
    db: AsyncSession, booking: Booking, new_status: BookingStatus
) -> Booking:
    """
    Update a booking's status after a payment outcome.

    Called by the payment service — not directly by the user.
    Enforces valid state transitions.

    :raises ValueError: if the transition is invalid.
    """
    if not is_valid_booking_transition(booking.status, new_status):
        raise ValueError(
            f"Invalid status transition: '{booking.status.value}' → '{new_status.value}'"
        )

    booking.status = new_status
    await db.commit()
    await db.refresh(booking)
    logger.info("Booking status updated: id=%s new_status=%s", booking.id, new_status.value)
    return booking
