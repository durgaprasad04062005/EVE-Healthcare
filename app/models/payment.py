"""
Payment model.

Represents a payment attempt for a booking.
One booking has at most one payment record (one-to-one).

Why one payment per booking?
For this system, a booking moves through a single payment attempt.
If payment fails, the booking is FAILED and a new booking must be
created for a retry. This keeps the data model simple and auditable.

payment_reference: a unique reference ID we generate (like a transaction ID)
provider_event_id: the event ID from the simulated payment provider,
                   used to correlate webhook events with this payment
"""

import enum

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # Each payment belongs to exactly one booking
    booking_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # enforces one payment per booking at the DB level
        index=True,
    )
    # Human-readable reference for the payment (e.g. to show the user)
    payment_reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    amount: Mapped[str] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="paymentstatus"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )
    # The event ID from the simulated payment provider.
    # Stored here so we can correlate incoming webhooks with this payment.
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # ORM relationship
    booking: Mapped["Booking"] = relationship("Booking", back_populates="payment")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} reference={self.payment_reference} status={self.status}>"
