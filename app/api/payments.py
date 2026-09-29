"""
Payments router.

Endpoints:
  POST /payments/          — initiate a simulated payment for a booking
  POST /payments/webhook/  — receive a simulated payment-status update (idempotent)

The payment endpoint requires authentication (the user must own the booking).
The webhook endpoint does NOT require user auth — it's called by the payment
provider (simulated here by the caller directly). In production you'd verify
a webhook signature instead.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.payment import PaymentRequest, PaymentResponse, WebhookPayload, WebhookResponse
from app.services import booking_service, payment_service

router = APIRouter()


@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a simulated payment for a booking",
    responses={
        400: {"description": "Booking is not payable (wrong status or already paid)"},
        403: {"description": "Booking belongs to a different user"},
        404: {"description": "Booking not found"},
    },
)
async def initiate_payment(
    data: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaymentResponse:
    """
    Initiate payment for a PENDING booking.

    - The booking must belong to the authenticated user.
    - The booking must be in PENDING status.
    - A booking can only have one payment.
    - The outcome (SUCCESS or FAILED) is randomly simulated.
    - On SUCCESS → booking becomes CONFIRMED.
    - On FAILED  → booking becomes FAILED.

    In a real system, this endpoint would redirect to a payment gateway.
    Here, the result is immediate and simulated.
    """
    # Load the booking
    booking = await booking_service.get_booking_by_id(db, data.booking_id)
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking '{data.booking_id}' not found",
        )

    # Authorization: the booking must belong to the current user
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to pay for this booking.",
        )

    try:
        payment = await payment_service.initiate_payment(db, booking)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PaymentResponse.model_validate(payment)


@router.post(
    "/webhook/",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive a simulated payment-status webhook",
    responses={
        200: {"description": "Event received (may be a duplicate — check 'received' field)"},
        400: {"description": "Invalid booking or payment reference"},
    },
)
async def payment_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """
    Receive a payment status update from the (simulated) payment provider.

    **Idempotency guarantee:**
    Sending the exact same event_id multiple times is safe.
    The first delivery is processed; subsequent deliveries with the same
    event_id are acknowledged (200 OK) but not reprocessed.

    The `received` field in the response indicates whether this was a
    new event (True) or a duplicate (False).

    In production, this endpoint would verify a webhook signature from
    the payment provider. That is not implemented here (no real provider).
    """
    try:
        is_new, message = await payment_service.process_webhook(db, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return WebhookResponse(
        received=is_new,
        event_id=payload.event_id,
        message=message,
    )
