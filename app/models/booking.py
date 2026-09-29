"""
Booking model.

A booking represents a patient's appointment to get a specific
diagnostic test done at a specific centre.

State machine:
  PENDING   — booking created, payment not yet processed
  CONFIRMED — payment succeeded
  FAILED    — payment failed
  CANCELLED — user cancelled before payment

Valid transitions:
  PENDING -> CONFIRMED  (payment success)
  PENDING -> FAILED     (payment failure)
  PENDING -> CANCELLED  (user cancels)

Invalid (must never happen):
  CONFIRMED -> PENDING
  FAILED -> CONFIRMED
  CANCELLED -> anything

The amount is taken from the CentreTest.price at booking time and
stored on the booking. This is intentional: if the price changes
later, historical bookings reflect what was charged at the time.
"""

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Which transitions are allowed from each state
VALID_BOOKING_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: set(),   # terminal state
    BookingStatus.FAILED: set(),      # terminal state
    BookingStatus.CANCELLED: set(),   # terminal state
}


def is_valid_booking_transition(current: BookingStatus, new: BookingStatus) -> bool:
    """Return True if transitioning from `current` to `new` is allowed."""
    return new in VALID_BOOKING_TRANSITIONS.get(current, set())


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_tests.id"), nullable=False
    )
    centre_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_centres.id"), nullable=False
    )
    appointment_datetime: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    # Amount locked in from CentreTest.price at booking creation time
    amount: Mapped[str] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="bookingstatus"),
        nullable=False,
        default=BookingStatus.PENDING,
    )

    # ORM relationships
    user: Mapped["User"] = relationship("User", back_populates="bookings")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest", back_populates="bookings")
    centre: Mapped["DiagnosticCentre"] = relationship("DiagnosticCentre", back_populates="bookings")
    payment: Mapped["Payment | None"] = relationship("Payment", back_populates="booking", uselist=False)

    def __repr__(self) -> str:
        return f"<Booking id={self.id} status={self.status}>"
