"""
Payment service.

Handles:
1. Initiating a simulated payment for a booking
2. Processing an incoming webhook event (idempotently)

NO real payment gateway is used. The outcome is randomly simulated.

Idempotency strategy:
- Every webhook event has a unique event_id.
- We attempt to INSERT a row into payment_webhook_events with that event_id.
- The table has UNIQUE(event_id) — so only ONE insert will succeed even
  under concurrent requests.
- If the INSERT fails with IntegrityError → duplicate → we return early
  without reprocessing, preserving the final state.
- The entire webhook processing (event insert + payment update + booking
  update) runs inside one database transaction, so partial failure is
  impossible.
"""

import random
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.webhook_event import PaymentWebhookEvent, WebhookEventStatus
from app.schemas.payment import WebhookPayload, WebhookPaymentStatus
from app.services import booking_service

logger = get_logger(__name__)

# Probability that a simulated payment succeeds.
# Set to 0.8 (80%) — realistic enough to test both outcomes easily.
SIMULATED_SUCCESS_RATE = 0.8


def _generate_payment_reference() -> str:
    """Generate a unique, human-readable payment reference."""
    return f"PAY-{uuid.uuid4().hex[:12].upper()}"


def _generate_provider_event_id() -> str:
    """Generate a simulated provider event ID."""
    return f"EVT-{uuid.uuid4().hex[:16].upper()}"


def _simulate_payment_outcome() -> PaymentStatus:
    """Randomly decide if the payment succeeds or fails."""
    return PaymentStatus.SUCCESS if random.random() < SIMULATED_SUCCESS_RATE else PaymentStatus.FAILED


async def get_payment_by_booking_id(db: AsyncSession, booking_id: str) -> Payment | None:
    """Return the Payment row for a given booking, or None."""
    result = await db.execute(
        select(Payment).where(Payment.booking_id == booking_id)
    )
    return result.scalar_one_or_none()


async def initiate_payment(
    db: AsyncSession, booking: Booking
) -> Payment:
    """
    Initiate a simulated payment for a booking.

    Validates:
    - The booking must be in PENDING status.
    - There must be no existing payment for this booking.

    Creates a Payment row, simulates the outcome, then updates the
    booking status accordingly — all in a single transaction.

    :raises ValueError: if the booking cannot be paid (wrong status, already paid).
    """
    if booking.status != BookingStatus.PENDING:
        raise ValueError(
            f"Cannot initiate payment for a booking with status '{booking.status.value}'. "
            "Only PENDING bookings can be paid."
        )

    # Check for existing payment (idempotency at the application layer)
    existing_payment = await get_payment_by_booking_id(db, booking.id)
    if existing_payment is not None:
        raise ValueError(
            f"A payment already exists for booking '{booking.id}' "
            f"(reference: {existing_payment.payment_reference}, "
            f"status: {existing_payment.status.value})."
        )

    # Simulate the payment outcome
    outcome = _simulate_payment_outcome()
    provider_event_id = _generate_provider_event_id()

    # Determine the booking status from the payment outcome
    new_booking_status = (
        BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS
        else BookingStatus.FAILED
    )

    # Create the payment record
    payment = Payment(
        booking_id=booking.id,
        payment_reference=_generate_payment_reference(),
        amount=booking.amount,
        status=outcome,
        provider_event_id=provider_event_id,
    )
    db.add(payment)

    # Update the booking status in the same transaction
    await booking_service.update_booking_status(db, booking, new_booking_status)

    await db.commit()
    await db.refresh(payment)

    logger.info(
        "Payment processed: booking=%s reference=%s outcome=%s",
        booking.id, payment.payment_reference, outcome.value
    )
    return payment


async def process_webhook(
    db: AsyncSession, payload: WebhookPayload
) -> tuple[bool, str]:
    """
    Process an incoming webhook event from the (simulated) payment provider.

    Returns:
        (is_new_event: bool, message: str)
        is_new_event = False means this was a duplicate and was ignored.

    Idempotency:
        We attempt to INSERT a PaymentWebhookEvent row with the unique event_id.
        If that INSERT raises IntegrityError (UNIQUE violation), the event was
        already processed — we return immediately without making any changes.

    Transaction:
        Everything (event INSERT + payment update + booking update) happens
        inside one database transaction. If the booking update fails, the
        event INSERT also rolls back, so the event can be retried.
    """
    # --- Step 1: Try to record this event (idempotency gate) ---
    event_record = PaymentWebhookEvent(
        event_id=payload.event_id,
        booking_id=payload.booking_id,
        payload=payload.model_dump_json(),
        status=WebhookEventStatus.RECEIVED,
    )

    try:
        db.add(event_record)
        # flush() sends the INSERT to the DB without committing.
        # If the event_id already exists, IntegrityError is raised here.
        await db.flush()
    except IntegrityError:
        # Duplicate event — roll back the failed flush and return early.
        await db.rollback()
        logger.info("Duplicate webhook event received and ignored: event_id=%s", payload.event_id)
        return False, f"Duplicate event '{payload.event_id}' — already processed"

    # --- Step 2: Look up the booking ---
    booking = await booking_service.get_booking_by_id(db, payload.booking_id)
    if booking is None:
        # Invalid booking ID — mark event as failed and commit
        event_record.status = WebhookEventStatus.FAILED
        await db.commit()
        raise ValueError(f"Booking '{payload.booking_id}' not found")

    # --- Step 3: Look up the payment ---
    payment = await get_payment_by_booking_id(db, payload.booking_id)
    if payment is None:
        event_record.status = WebhookEventStatus.FAILED
        await db.commit()
        raise ValueError(f"No payment found for booking '{payload.booking_id}'")

    # --- Step 4: Determine the new statuses from the webhook payload ---
    if payload.status == WebhookPaymentStatus.SUCCESS:
        new_payment_status = PaymentStatus.SUCCESS
        new_booking_status = BookingStatus.CONFIRMED
    else:
        new_payment_status = PaymentStatus.FAILED
        new_booking_status = BookingStatus.FAILED

    # --- Step 5: Only update if the booking is still in a transitionable state ---
    # It's valid for the booking to already be CONFIRMED/FAILED (from the direct
    # payment endpoint), in which case the webhook is just confirming what we know.
    from app.models.booking import is_valid_booking_transition
    if is_valid_booking_transition(booking.status, new_booking_status):
        payment.status = new_payment_status
        await booking_service.update_booking_status(db, booking, new_booking_status)
        logger.info(
            "Webhook processed: event=%s booking=%s new_status=%s",
            payload.event_id, payload.booking_id, new_booking_status.value
        )
    else:
        # The booking is already in a terminal state — webhook is redundant but valid.
        # We still record the event but don't change anything.
        logger.info(
            "Webhook for already-terminal booking: event=%s booking=%s current_status=%s",
            payload.event_id, payload.booking_id, booking.status.value
        )

    # --- Step 6: Commit everything ---
    await db.commit()
    return True, f"Event '{payload.event_id}' processed successfully"
