"""
Pydantic schemas for the Payment resource and Webhook endpoint.
"""

import enum
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus


class PaymentRequest(BaseModel):
    """
    Request body for POST /payments/

    The caller provides only the booking_id.
    All other details (amount, test, centre) are derived from the booking.
    """
    booking_id: str = Field(..., description="The booking to pay for")


class PaymentResponse(BaseModel):
    """Response after initiating a payment."""
    id: str
    booking_id: str
    payment_reference: str
    amount: Decimal
    status: PaymentStatus
    # The simulated provider event ID — used in webhook calls
    provider_event_id: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Webhook schemas
# ---------------------------------------------------------------------------

class WebhookPaymentStatus(str, enum.Enum):
    """The payment outcome as reported by the simulated payment provider."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WebhookPayload(BaseModel):
    """
    The payload sent to POST /payments/webhook/

    In a real system this would come from Stripe/PayFast/etc.
    Here we simulate it with a simple JSON body.

    event_id:   Unique ID for this event (the idempotency key).
                Must be the same value for retries of the same event.
    booking_id: The booking this payment relates to.
    status:     Whether the payment succeeded or failed.
    """
    event_id: str = Field(..., description="Unique event ID (idempotency key)")
    booking_id: str = Field(..., description="Booking ID this payment relates to")
    status: WebhookPaymentStatus = Field(..., description="Payment outcome: SUCCESS or FAILED")


class WebhookResponse(BaseModel):
    """Response from the webhook endpoint."""
    received: bool
    event_id: str
    message: str
