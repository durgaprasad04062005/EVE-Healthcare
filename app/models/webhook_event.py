"""
PaymentWebhookEvent model — the idempotency store.

This table is the core of our idempotency strategy.

How it works:
1. When a webhook arrives, we attempt to INSERT a row with the event_id.
2. The `event_id` column has a UNIQUE constraint at the database level.
3. If the same event_id arrives again (duplicate), the INSERT fails with
   an IntegrityError — which we catch and return a 200 OK without
   reprocessing.
4. The status column tracks whether processing succeeded or failed,
   which is useful for debugging and auditing.

Why database-level uniqueness and not just an in-memory dict?
- In-memory state is lost on restart.
- Multiple server instances would not share in-memory state.
- The database UNIQUE constraint is atomic — even concurrent duplicate
  requests will result in only one succeeding.

event_id: the unique event identifier provided by the payment provider
          (in our simulated system, we generate this UUID when calling
          POST /payments/ and include it in the simulated webhook payload)
"""

import enum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class WebhookEventStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"    # successfully received and processed
    DUPLICATE = "DUPLICATE"  # duplicate — ignored
    FAILED = "FAILED"        # processing raised an unexpected error


class PaymentWebhookEvent(Base, TimestampMixin):
    __tablename__ = "payment_webhook_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # The unique event ID from the payment provider.
    # UNIQUE constraint is the database-level idempotency guard.
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # The booking this event relates to (stored for auditing/debugging)
    booking_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Raw payload stored for auditability — useful if you need to replay events
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[WebhookEventStatus] = mapped_column(
        Enum(WebhookEventStatus, name="webhookeventstatus"),
        nullable=False,
        default=WebhookEventStatus.RECEIVED,
    )

    def __repr__(self) -> str:
        return f"<PaymentWebhookEvent event_id={self.event_id} status={self.status}>"
